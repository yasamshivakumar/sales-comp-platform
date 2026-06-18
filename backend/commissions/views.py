from datetime import datetime
from rest_framework import status
import csv
import io
import logging
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework import viewsets
from .models import (
    Employee,
    Sale,
    Commission,
    UserProfile,
    HierarchyRelationship,
    CompensationPlan,
    CompensationTier,
    Order,
)
from decimal import Decimal, InvalidOperation
from .serializers import (
    EmployeeSerializer,
    CommissionSerializer,
    CompensationPlanSerializer,
    CompensationTierSerializer,
    OrderSerializer,
)
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from .serializers import UserProfileSerializer, HierarchyRelationshipSerializer
from django.conf import settings
from .services import (
    calculate_commission_for_order,
    approve_commissions,
    recalculate_orders_in_range,
)
from .permissions import (
    require_admin,
    require_finance_or_admin,
    user_is_admin,
    user_is_finance,
    user_is_manager,
    user_can_view_finance_data,
    get_request_user_profile,
)
from .audit import record_audit
from .emails import notify_admins
from .models import AuditLog, ImportJob
from .imports import process_orders_csv, should_use_async_import
from .list_scope import order_search_q
from .tenants import filter_queryset_by_organization


def _orders_queryset_for_request(request):
    """Orders visible to the user, with commission data prefetched."""
    queryset = filter_queryset_by_organization(
        Order.objects.select_related("sale_record")
        .prefetch_related(
            Prefetch(
                "sale_record__commission_set",
                queryset=Commission.objects.order_by("id"),
            )
        )
        .order_by("-order_date", "-id"),
        getattr(request, "organization", None),
    )

    search_term = (
        request.query_params.get("q") or request.query_params.get("search") or ""
    ).strip()
    if search_term:
        queryset = queryset.filter(order_search_q(search_term))
    else:
        status_filter = (request.query_params.get("order_status") or "").strip()
        if status_filter:
            queryset = queryset.filter(order_status__iexact=status_filter)

    user = request.user
    try:
        user_profile = UserProfile.objects.get(email=user.email)
        is_admin = user_profile.role.lower() in ["admin", "administrator"]
        if is_admin:
            return queryset
        if user_profile.employee_id:
            return queryset.filter(employee_id=user_profile.employee_id)
        return queryset.filter(employee_email=user.email)
    except UserProfile.DoesNotExist:
        return queryset.none()

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse
from django.utils.dateparse import parse_date

logger = logging.getLogger("commissions")


from .user_scope import profile_commission_q
from .auth_utils import provision_login_user


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer


class CommissionViewSet(viewsets.ModelViewSet):
    serializer_class = CommissionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Filter commissions based on user role:
        - Admin: Can see all commissions
        - Regular employee: Can only see their own commissions
        """
        user = self.request.user
        
        try:
            user_profile = UserProfile.objects.get(email=user.email)
            is_admin = user_profile.role.lower() in ['admin', 'administrator']
            is_finance = user_is_finance(self.request)
            is_manager = user_is_manager(self.request)
            
            if is_admin or is_finance or is_manager:
                queryset = Commission.objects.select_related(
                    "employee",
                    "sale",
                    "sale__order",
                    "compensation_plan",
                    "approved_by",
                    "manager_approved_by",
                    "payout_run",
                ).all()
                queryset = filter_queryset_by_organization(
                    queryset,
                    getattr(self.request, "organization", None),
                    field="sale__order__organization",
                )
            else:
                from django.db.models import Q

                query = profile_commission_q(user_profile, user.email)
                queryset = Commission.objects.filter(query).select_related(
                    "employee",
                    "sale",
                    "sale__order",
                    "compensation_plan",
                )
        except UserProfile.DoesNotExist:
            queryset = Commission.objects.filter(
                employee__email=user.email
            ).select_related("employee", "sale", "sale__order")

        status_filter = self.request.query_params.get("status")
        valid_statuses = {c[0] for c in Commission.STATUS_CHOICES}
        if status_filter in valid_statuses:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def _payroll_can_see_all(self, request):
        try:
            user_profile = UserProfile.objects.get(email=request.user.email)
            role = user_profile.role.lower()
            return (
                role in ["admin", "administrator"]
                or user_is_finance(request)
                or user_is_manager(request)
            )
        except UserProfile.DoesNotExist:
            return False

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if self._payroll_can_see_all(request):
            from .list_scope import commission_employee_search_q, list_limit_for_request

            q = (request.query_params.get("q") or "").strip()
            if q:
                queryset = queryset.filter(commission_employee_search_q(q))
            limit = list_limit_for_request(request, searching=bool(q))
            total_count = queryset.count()
            queryset = queryset.order_by("-calculated_at", "-id")[:limit]
            serializer = self.get_serializer(queryset, many=True)
            return Response(
                {
                    "results": serializer.data,
                    "count": total_count,
                    "limited": total_count > limit,
                }
            )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def signup(request):
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')

    # Validate required fields
    if not username or not password:
        return Response(
            {'error': 'Username and password are required'},
            status=400
        )

    # Check if username already exists
    if User.objects.filter(username=username).exists():
        return Response(
            {'error': 'Username already exists'},
            status=400
        )

    # Create user
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password
    )

    # Create authentication token
    token, _ = Token.objects.get_or_create(user=user)

    # Return success response
    return Response({
        'message': 'User created successfully',
        'token': token.key
    })


signup.throttle_scope = "login"


class CompensationPlanListCreateView(generics.ListCreateAPIView):
    serializer_class = CompensationPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = CompensationPlan.objects.prefetch_related(
            "sc_rate_tables",
            "sc_flat_rate_tables",
            "sc_lookup_tables",
            "commission_rules",
        ).order_by("-created_at")
        return filter_queryset_by_organization(
            qs, getattr(self.request, "organization", None)
        )

    def perform_create(self, serializer):
        serializer.save(organization=getattr(self.request, "organization", None))

    def check_admin_permission(self, request):
        if not user_is_admin(request):
            raise PermissionDenied("Only administrators can access compensation plans")
        return True

    def list(self, request, *args, **kwargs):
        self.check_admin_permission(request)
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        self.check_admin_permission(request)
        return super().create(request, *args, **kwargs)


class CompensationPlanDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = CompensationPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = CompensationPlan.objects.prefetch_related(
            "sc_rate_tables",
            "sc_flat_rate_tables",
            "sc_lookup_tables",
            "commission_rules",
            "commission_rules__conditions",
            "commission_rules__results",
        )
        return filter_queryset_by_organization(
            qs, getattr(self.request, "organization", None)
        )

    def check_admin_permission(self, request):
        if not user_is_admin(request):
            raise PermissionDenied("Only administrators can access compensation plans")
        return True

    def retrieve(self, request, *args, **kwargs):
        self.check_admin_permission(request)
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self.check_admin_permission(request)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self.check_admin_permission(request)
        return super().partial_update(request, *args, **kwargs)


class UserProfileListCreateView(generics.ListCreateAPIView):

    queryset = UserProfile.objects.all().order_by('first_name')
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from .list_scope import profile_search_q

        qs = UserProfile.objects.all().order_by("first_name")
        qs = filter_queryset_by_organization(
            qs, getattr(self.request, "organization", None)
        )
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(profile_search_q(q))
        return qs

    def list(self, request, *args, **kwargs):
        from .list_scope import list_limit_for_request

        queryset = self.filter_queryset(self.get_queryset())
        q = (request.query_params.get("q") or "").strip()
        limit = list_limit_for_request(request, searching=bool(q))
        page = queryset[:limit]
        serializer = self.get_serializer(page, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):

        try:
            data = request.data.copy()

            # ---------------------------------------------------
            # Required Field
            # ---------------------------------------------------
            email = str(
                data.get('email', '')
            ).strip()

            if not email:
                return Response(
                    {'error': 'Email is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            from .field_rules import validate_user_profile_fields
            from rest_framework.exceptions import ValidationError as DRFValidationError

            try:
                validate_user_profile_fields(data)
            except DRFValidationError as exc:
                detail = exc.detail
                if isinstance(detail, dict):
                    detail = "; ".join(
                        f"{k}: {v[0] if isinstance(v, list) else v}"
                        for k, v in detail.items()
                    )
                return Response({"error": str(detail)}, status=status.HTTP_400_BAD_REQUEST)

            # ---------------------------------------------------
            # Boolean Conversion
            # ---------------------------------------------------
            enable_login = str(
                data.get('enable_login', 'False')
            ).strip().lower() in ['true', '1', 'yes']

            # ---------------------------------------------------
            # Numeric Fields
            # ---------------------------------------------------
            personal_target = (
                data.get('personal_target') or 0
            )

            split_percentage = (
                data.get('split_percentage') or 100
            )

            # ---------------------------------------------------
            # Username
            # ---------------------------------------------------
            username = str(
                data.get('username', '')
            ).strip()

            if not username:
                username = email

            employee_id = str(data.get("employee_id", "")).strip()

            # ---------------------------------------------------
            # Reject duplicate users (email / employee_id within org)
            # ---------------------------------------------------
            from .field_rules import find_user_profile_duplicates

            org = getattr(request, "organization", None)
            dup_errors = find_user_profile_duplicates(org, email, employee_id)
            if dup_errors:
                return Response(
                    {"error": " ".join(dup_errors)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ---------------------------------------------------
            # Create UserProfile
            # ---------------------------------------------------
            profile = UserProfile.objects.create(
                organization=org,
                enable_login=enable_login,
                name=str(data.get("name", "")).strip(),
                email=email,
                role=str(data.get("role", "Sales Rep")).strip(),
                username=username,
                first_name=str(data.get("first_name", "")).strip(),
                last_name=str(data.get("last_name", "")).strip(),
                prefix=str(data.get("prefix", "")).strip(),
                employee_id=employee_id,
                hire_date=data.get("hire_date"),
                personal_target=personal_target,
                personal_currency=str(
                    data.get("personal_currency", "INR")
                ).strip(),
                business_group=str(
                    data.get("business_group", "India")
                ).strip(),
                title=str(data.get("title", "")).strip(),
                pay_period_type=str(
                    data.get("pay_period_type", "Monthly")
                ).strip(),
                position_name=str(data.get("position_name", "")).strip(),
                position_title=str(data.get("position_title", "")).strip(),
            )
            territory_id = data.get("territory")
            if territory_id:
                profile.territory_id = territory_id
                profile.save(update_fields=["territory"])

            # ---------------------------------------------------
            # Create Django Auth User
            # ---------------------------------------------------
            if enable_login:
                provision_login_user(profile)

            # ---------------------------------------------------
            # Hierarchy Relationship
            # ---------------------------------------------------
            parent_participant = data.get(
                'parent_participant'
            )

            child_participant = data.get(
                'child_participant'
            )

            if parent_participant and child_participant:

                parent_profile = UserProfile.objects.filter(
                    id=parent_participant
                ).first()

                child_profile = UserProfile.objects.filter(
                    id=child_participant
                ).first()

                if parent_profile and child_profile:

                    HierarchyRelationship.objects.update_or_create(
                        parent_participant=parent_profile,
                        child_participant=child_profile,
                        defaults={
                            'split_percentage': split_percentage,
                            'is_active': True,
                        }
                    )

            serializer = self.get_serializer(profile)

            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:

            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class UserProfileUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "upload"

    @transaction.atomic
    def post(self, request):
        # ---------------------------------------------------
        # Check file exists
        # ---------------------------------------------------
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file uploaded'},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_file = request.FILES['file']

        # ---------------------------------------------------
        # This version supports CSV files only
        # ---------------------------------------------------
        if not uploaded_file.name.lower().endswith('.csv'):
            return Response(
                {'error': 'Only CSV files are supported'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Read CSV file
            decoded_file = uploaded_file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(decoded_file))
            rows = list(csv_reader)

        except Exception as e:
            return Response(
                {'error': f'Error reading CSV file: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        success = 0
        failed = 0
        errors = []
        
        # Cache for lookups to reduce database queries
        email_to_profile = {}
        username_to_profile = {}
        employee_id_to_profile = {}

        # ---------------------------------------------------
        # Process each row with batch optimization
        # ---------------------------------------------------
        for index, row in enumerate(rows, start=2):
            try:
                # ---------------------------------------------------
                # Required field: Email
                # ---------------------------------------------------
                email = str(row.get('email', '')).strip().lower()

                if not email:
                    raise Exception('Email is required')

                role_val = str(row.get('role', '')).strip()
                employee_id_val = str(row.get('employee_id', '')).strip()
                name_val = str(row.get('name', '')).strip()
                if not role_val:
                    raise Exception('role is required')
                if not employee_id_val:
                    raise Exception('employee_id is required')
                if not name_val:
                    raise Exception('name is required')

                # ---------------------------------------------------
                # Boolean conversion for enable_login
                # Accepts: yes, true, 1
                # ---------------------------------------------------
                enable_login = str(
                    row.get('enable_login', 'False')
                ).strip().lower() in ['true', '1', 'yes']

                # ---------------------------------------------------
                # Numeric conversion
                # ---------------------------------------------------
                personal_target = row.get('personal_target', 0)
                if personal_target in ['', None]:
                    personal_target = 0
                personal_target = float(personal_target)

                split_percentage = row.get('split_percentage', 100)
                if split_percentage in ['', None]:
                    split_percentage = 100
                split_percentage = float(split_percentage)

                # ---------------------------------------------------
                # Date conversion
                # Supports:
                # - 12-03-2026
                # - 12/03/2026
                # - 2026-03-12
                # ---------------------------------------------------
                hire_date = row.get('hire_date', '')

                if hire_date in ['', None]:
                    hire_date = None
                else:
                    hire_date_str = str(hire_date).strip()

                    parsed_date = None
                    date_formats = [
                        '%d-%m-%Y',
                        '%d/%m/%Y',
                        '%Y-%m-%d',
                    ]

                    for fmt in date_formats:
                        try:
                            parsed_date = datetime.strptime(
                                hire_date_str,
                                fmt
                            ).date()
                            break
                        except ValueError:
                            pass

                    if parsed_date is None:
                        raise Exception(
                            f'Invalid hire_date format: {hire_date_str}. '
                            f'Use DD-MM-YYYY or YYYY-MM-DD.'
                        )

                    hire_date = parsed_date

                # ---------------------------------------------------
                # Username for login
                # Priority:
                # 1. username column
                # 2. email
                # ---------------------------------------------------
                username = str(
                    row.get('username', '')
                ).strip()

                if not username:
                    username = email

                # ---------------------------------------------------
                # Reject duplicates, then create UserProfile
                # ---------------------------------------------------
                org = getattr(request, "organization", None)

                from .field_rules import find_user_profile_duplicates

                dup_errors = find_user_profile_duplicates(
                    org, email, employee_id_val
                )
                if dup_errors:
                    raise Exception(" ".join(dup_errors))

                profile = UserProfile.objects.create(
                    organization=org,
                    enable_login=enable_login,
                    name=name_val,
                    role=role_val,
                    email=email,
                    username=username,
                    first_name=str(row.get('first_name', '')).strip(),
                    last_name=str(row.get('last_name', '')).strip(),
                    prefix=str(row.get('prefix', '')).strip(),
                    employee_id=employee_id_val,
                    hire_date=hire_date,
                    personal_target=personal_target,
                    personal_currency=str(
                        row.get('personal_currency', 'INR')
                    ).strip(),
                    business_group=str(
                        row.get('business_group', 'India')
                    ).strip(),
                    title=str(row.get('title', '')).strip(),
                    pay_period_type=str(
                        row.get('pay_period_type', 'Monthly')
                    ).strip(),
                    position_name=str(
                        row.get('position_name', '')
                    ).strip(),
                    position_title=str(
                        row.get('position_title', '')
                    ).strip(),
                )
                
                # Update cache
                email_to_profile[email] = profile
                username_to_profile[username] = profile
                if profile.employee_id:
                    employee_id_to_profile[profile.employee_id] = profile

                # ---------------------------------------------------
                # Create Django Login User
                #
                # If enable_login = yes/true/1,
                # create a Django auth user.
                #
                # Login: password set only if DEFAULT_ONBOARDING_PASSWORD is in .env
                # ---------------------------------------------------
                if enable_login:
                    provision_login_user(profile)

                # ---------------------------------------------------
                # Create Hierarchy Relationship
                # Lookup by username, employee_id, or email
                # Uses cache to reduce database queries
                # ---------------------------------------------------
                parent_value = str(
                    row.get('parent_participant', '')
                ).strip()

                child_value = str(
                    row.get('child_participant', '')
                ).strip()

                if parent_value and child_value:
                    # Try cache first, then database
                    parent_profile = (
                        username_to_profile.get(parent_value)
                        or employee_id_to_profile.get(parent_value)
                        or email_to_profile.get(parent_value)
                        or UserProfile.objects.filter(
                            username=parent_value
                        ).first()
                        or UserProfile.objects.filter(
                            employee_id=parent_value
                        ).first()
                        or UserProfile.objects.filter(
                            email=parent_value
                        ).first()
                    )

                    child_profile = (
                        username_to_profile.get(child_value)
                        or employee_id_to_profile.get(child_value)
                        or email_to_profile.get(child_value)
                        or UserProfile.objects.filter(
                            username=child_value
                        ).first()
                        or UserProfile.objects.filter(
                            employee_id=child_value
                        ).first()
                        or UserProfile.objects.filter(
                            email=child_value
                        ).first()
                    )

                    if parent_profile and child_profile:
                        HierarchyRelationship.objects.update_or_create(
                            parent_participant=parent_profile,
                            child_participant=child_profile,
                            defaults={
                                'split_percentage': split_percentage,
                                'is_active': True,
                            }
                        )

                # ---------------------------------------------------
                # Row processed successfully
                # ---------------------------------------------------
                success += 1

            except Exception as e:
                failed += 1
                errors.append({
                    'row': index,
                    'email': row.get('email', ''),
                    'error': str(e),
                })
                logger.error(
                    f"Error processing row {index}: {str(e)}"
                )

        # ---------------------------------------------------
        # Final response
        # ---------------------------------------------------
        payload = {
            "message": "Upload completed successfully",
            "success": success,
            "failed": failed,
            "errors": errors[:20],
        }
        if getattr(settings, "DEFAULT_ONBOARDING_PASSWORD", ""):
            payload["note"] = (
                "New login users received the password from DEFAULT_ONBOARDING_PASSWORD. "
                "Change it after first login."
            )
        record_audit(
            request,
            "user_setup_upload",
            {"success": success, "failed": failed, "filename": uploaded_file.name},
        )
        return Response(payload)


class HierarchyRelationshipListCreateView(generics.ListCreateAPIView):
    queryset = HierarchyRelationship.objects.filter(
        is_active=True
    ).order_by('parent_participant') 

    serializer_class = HierarchyRelationshipSerializer
    permission_classes = [IsAuthenticated]


class CompensationTierListCreateView(generics.ListCreateAPIView):
    queryset = CompensationTier.objects.all().order_by('plan', 'min_sales')
    serializer_class = CompensationTierSerializer
    permission_classes = [IsAuthenticated]



class OrderListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/orders/   -> List all uploaded orders (filtered by role)
    POST /api/orders/   -> Create a single order manually
    
    Access Control:
    - Admin: Can see all orders, can create/update/delete orders
    - Regular employee: Can only see their own orders, cannot create/modify
    """
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return _orders_queryset_for_request(self.request)

    def perform_create(self, serializer):
        order = serializer.save(
            organization=getattr(self.request, "organization", None)
        )
        calculate_commission_for_order(order)


class OrderDetailView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH /api/orders/<id>/

    Updating an order (e.g. Booked → Success) recalculates commission when eligible.
    """
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _orders_queryset_for_request(self.request)

    def perform_update(self, serializer):
        if not user_is_admin(self.request):
            raise PermissionDenied("Only administrators can update orders")
        order = serializer.save()
        calculate_commission_for_order(order)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        refreshed = (
            self.get_queryset()
            .select_related("sale_record")
            .prefetch_related("sale_record__commission_set")
            .get(pk=instance.pk)
        )
        return Response(self.get_serializer(refreshed).data)


class OrderUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "upload"

    def post(self, request):
        # ---------------------------------------------------
        # Check file exists
        # ---------------------------------------------------
        if "file" not in request.FILES:
            return Response(
                {"error": "No file uploaded"},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_file = request.FILES["file"]

        # ---------------------------------------------------
        # Support CSV files only
        # ---------------------------------------------------
        if not uploaded_file.name.lower().endswith(".csv"):
            return Response(
                {"error": "Only CSV files are supported"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ---------------------------------------------------
        # Read CSV file
        # ---------------------------------------------------
        try:
            decoded_file = uploaded_file.read().decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(decoded_file)))
        except Exception as e:
            return Response(
                {"error": f"Error reading CSV file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        organization = getattr(request, "organization", None)
        if not organization:
            return Response(
                {"error": "Organization context missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if should_use_async_import(len(rows)):
            from .tasks import process_import_job_task

            job = ImportJob.objects.create(
                organization=organization,
                created_by=request.user,
                job_type=ImportJob.JOB_ORDERS,
                source_filename=uploaded_file.name,
                row_count=len(rows),
            )
            job.input_file.save(
                uploaded_file.name,
                ContentFile(decoded_file.encode("utf-8")),
                save=True,
            )
            process_import_job_task.delay(job.id)
            record_audit(
                request,
                "orders_upload_queued",
                {"job_id": job.id, "rows": len(rows), "filename": uploaded_file.name},
            )
            return Response(
                {
                    "message": "Import queued for background processing",
                    "async": True,
                    "job_id": job.id,
                    "status": job.status,
                    "row_count": len(rows),
                },
                status=status.HTTP_202_ACCEPTED,
            )

        summary = process_orders_csv(organization, decoded_file)
        record_audit(
            request,
            "orders_upload",
            {
                "success": summary["success"],
                "failed": summary["failed"],
                "filename": uploaded_file.name,
            },
        )
        notify_admins(
            "Incentra: order upload finished",
            (
                f"User: {request.user.email}\n"
                f"File: {uploaded_file.name}\n"
                f"Success: {summary['success']}\n"
                f"Failed: {summary['failed']}\n"
            ),
        )
        return Response({
            "message": "Order upload completed successfully",
            "async": False,
            **summary,
        })


# =====================================================
# Email-Based Login
# =====================================================
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def email_login(request):
    """
    Login endpoint that accepts email and password.
    
    Request body:
    {
        "email": "user@example.com",
        "password": "password123"
    }
    
    Response:
    {
        "message": "Login successful",
        "token": "auth_token_here",
        "email": "user@example.com",
        "role": "Sales Rep",
        "user_id": 1
    }
    """
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password')
    
    if not email or not password:
        return Response(
            {'error': 'Email and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    profile = (
        UserProfile.objects.filter(email__iexact=email, enable_login=True).first()
        or UserProfile.objects.filter(employee_id__iexact=email, enable_login=True).first()
    )

    user = User.objects.filter(email__iexact=email).first()
    if not user:
        user = User.objects.filter(username__iexact=email).first()
    if not user and profile:
        user = User.objects.filter(email__iexact=profile.email).first()
    if not user and profile:
        user = User.objects.filter(username__iexact=profile.username).first()
    if not user and profile:
        user = provision_login_user(profile)

    if not user:
        logger.warning(f"Login attempt with non-existent email: {email}")
        record_audit(request, "login_failed", {"email": email})
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Check password (username is the canonical auth field in Django)
    if not user.check_password(password):
        auth_user = authenticate(request, username=user.username, password=password)
        if not auth_user:
            auth_user = authenticate(request, username=user.email, password=password)
        if not auth_user and profile:
            repaired = provision_login_user(profile)
            if repaired and repaired.check_password(password):
                auth_user = repaired
        if not auth_user:
            logger.warning(f"Failed login attempt for email: {email}")
            record_audit(request, "login_failed", {"email": email})
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        user = auth_user
    
    # Check if user is active
    if not user.is_active:
        return Response(
            {'error': 'User account is inactive'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Get or create token
        token, _ = Token.objects.get_or_create(user=user)
        
        # Get user profile for additional info
        user_profile = UserProfile.objects.filter(email=user.email).first()
        
        logger.info(f"Successful login for email: {email}")
        record_audit(request, "login_success", {"user_id": user.id, "email": email})
        
        return Response({
            'message': 'Login successful',
            'token': token.key,
            'email': user.email,
            'user_id': user.id,
            'role': user_profile.role if user_profile else 'Sales Rep',
            'name': user_profile.name if user_profile else user.get_full_name() or user.username,
        })
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return Response(
            {'error': 'An error occurred during login'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


email_login.throttle_scope = "login"


# =====================================================
# Change Password
# =====================================================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change user password endpoint.
    
    Request body:
    {
        "old_password": "current_password",
        "new_password": "new_password123"
    }
    
    Response:
    {
        "message": "Password changed successfully"
    }
    """
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    
    if not old_password or not new_password:
        return Response(
            {'error': 'Both old and new passwords are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if len(new_password) < 8:
        return Response(
            {'error': 'Password must be at least 8 characters long'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Verify old password
        if not user.check_password(old_password):
            logger.warning(f"Failed password change attempt for user: {user.email}")
            return Response(
                {'error': 'Old password is incorrect'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        # Invalidate all tokens to force re-login on other devices
        Token.objects.filter(user=user).delete()
        
        # Create new token for current session
        token, _ = Token.objects.get_or_create(user=user)
        
        logger.info(f"Password changed successfully for user: {user.email}")
        
        return Response({
            'message': 'Password changed successfully',
            'token': token.key
        })
        
    except Exception as e:
        logger.error(f"Password change error: {str(e)}")
        return Response(
            {'error': 'An error occurred while changing password'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =====================================================
# Get User Profile (for role-based access control)
# =====================================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    """
    Get current user's profile and role information.
    
    Response:
    {
        "user_id": 1,
        "email": "user@example.com",
        "role": "Sales Rep",
        "name": "John Doe",
        "is_admin": false,
        "employee_id": "EMP001"
    }
    """
    user = request.user
    
    try:
        user_profile = UserProfile.objects.get(email=user.email)
        is_admin = user_profile.role.lower() in ['admin', 'administrator']
        
        org = user_profile.organization
        return Response({
            'user_id': user.id,
            'email': user.email,
            'role': user_profile.role,
            'name': user_profile.name,
            'is_admin': is_admin,
            'is_finance': user_is_finance(request),
            'is_manager': user_is_manager(request),
            'employee_id': user_profile.employee_id,
            'territory_id': user_profile.territory_id,
            'territory_name': (
                user_profile.territory.name if user_profile.territory_id else None
            ),
            'business_group': user_profile.business_group or '',
            'personal_currency': user_profile.personal_currency or 'INR',
            'organization_slug': org.slug if org else None,
            'organization_name': org.name if org else None,
        })
        
    except UserProfile.DoesNotExist:
        return Response(
            {'error': 'User profile not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}")
        return Response(
            {'error': 'An error occurred'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _profile_display_name(profile):
    if not profile:
        return ""
    full = f"{profile.first_name} {profile.last_name}".strip()
    return full or (profile.name or "").strip() or profile.email


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_directory(request):
    """Employees for order-form search with position, manager, and territory."""
    from .list_scope import list_limit_for_request, profile_search_q

    org = getattr(request, "organization", None)
    profiles = filter_queryset_by_organization(
        UserProfile.objects.exclude(employee_id="")
        .exclude(employee_id__isnull=True)
        .select_related("territory"),
        org,
    ).order_by("employee_id")

    query = (request.query_params.get("q") or "").strip()
    if query:
        profiles = profiles.filter(profile_search_q(query))

    limit = list_limit_for_request(request, searching=bool(query))
    profile_list = list(profiles[:limit])
    profile_ids = [profile.id for profile in profile_list]
    manager_by_child = {}
    if profile_ids:
        for rel in HierarchyRelationship.objects.filter(
            child_participant_id__in=profile_ids
        ).select_related("parent_participant"):
            manager_by_child[rel.child_participant_id] = rel.parent_participant

    results = []
    for profile in profile_list:
        manager = manager_by_child.get(profile.id)
        results.append(
            {
                "id": profile.id,
                "employee_id": profile.employee_id,
                "display_name": _profile_display_name(profile),
                "position_name": profile.position_name or "",
                "business_group": profile.business_group or "",
                "manager_name": _profile_display_name(manager) if manager else "",
                "territory_id": profile.territory_id,
                "territory_name": profile.territory.name if profile.territory else "",
            }
        )

    return Response(results)


# =====================================================
# REPORTS API
# =====================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def commission_summary_report(request):
    """
    Commission Summary Report
    Shows total commissions, top earners, metrics
    Admin: All employees, Employee: Own only
    """
    from django.db.models import Sum, Count, Q, Avg
    from django.utils.dateparse import parse_date
    
    user = request.user
    user_profile = None
    try:
        user_profile = UserProfile.objects.get(email=user.email)
        is_admin = user_profile.role.lower() in ['admin', 'administrator']
    except UserProfile.DoesNotExist:
        is_admin = False
    
    start_date = parse_date(request.query_params.get("start_date") or "")
    end_date = parse_date(request.query_params.get("end_date") or "")
    
    from .business_groups import (
        apply_business_group_to_commissions,
        business_group_choices_for_api,
        commission_totals_by_business_group,
        currency_for_business_group,
        resolve_dashboard_business_group,
    )
    from .permissions import user_is_finance

    can_view_all_groups = is_admin or user_is_finance(request)
    effective_group, view_all_groups, available_groups = resolve_dashboard_business_group(
        request, user_profile, can_view_all_groups
    )

    commissions = Commission.objects.all()
    org = getattr(request, "organization", None)
    if org:
        commissions = commissions.filter(sale__order__organization=org)

    if start_date and end_date:
        commissions = commissions.filter(
            sale__order__order_date__range=[start_date, end_date]
        )
    elif start_date:
        commissions = commissions.filter(sale__order__order_date__gte=start_date)
    elif end_date:
        commissions = commissions.filter(sale__order__order_date__lte=end_date)
    
    # Filter by role
    if not is_admin and not user_is_finance(request):
        possible_emails = [user.email]
        if user_profile and user_profile.employee_id:
            possible_emails.append(f"{user_profile.employee_id}@company.com")
        commissions = commissions.filter(employee__email__in=possible_emails)

    base_commissions = commissions
    commissions = apply_business_group_to_commissions(commissions, effective_group)
    
    from .currencies import active_currency_totals, normalize_currency, primary_currency_from_totals

    total_commission = commissions.aggregate(Sum('commission_amount'))['commission_amount__sum'] or 0
    total_count = commissions.count()
    avg_commission = commissions.aggregate(Avg('commission_amount'))['commission_amount__avg'] or 0
    active_reps_count = commissions.values('employee_id').distinct().count()

    personal_currency = normalize_currency(
        user_profile.personal_currency if user_profile else None
    )
    by_business_group = (
        commission_totals_by_business_group(base_commissions) if view_all_groups else []
    )
    if effective_group:
        primary_currency = currency_for_business_group(effective_group, personal_currency)
    else:
        primary_currency = primary_currency_from_totals(
            [
                {"currency": row["currency"], "total": row["total"]}
                for row in by_business_group
            ],
            fallback=personal_currency,
        )
    totals_by_currency = (
        active_currency_totals(
            [{"currency": primary_currency, "total": float(total_commission)}]
        )
        if effective_group
        else active_currency_totals(
            [
                {"currency": row["currency"], "total": row["total"]}
                for row in by_business_group
            ]
        )
    )

    # Top earners (only for admin)
    top_earners = []
    if is_admin:
        for row in commissions.values('employee__name', 'employee__email').annotate(
            total=Sum('commission_amount'),
            count=Count('id'),
        ).order_by('-total')[:5]:
            profile = UserProfile.objects.filter(email=row["employee__email"]).first()
            top_earners.append(
                {
                    **row,
                    "business_group": profile.business_group if profile else "",
                    "currency": currency_for_business_group(
                        profile.business_group if profile else effective_group,
                        profile.personal_currency if profile else primary_currency,
                    ),
                }
            )

    return Response({
        'total_commission': float(total_commission),
        'total_count': total_count,
        'avg_commission': float(avg_commission),
        'active_reps_count': active_reps_count,
        'totals_by_currency': totals_by_currency,
        'by_business_group': by_business_group,
        'business_group': effective_group,
        'view_all_business_groups': view_all_groups,
        'available_business_groups': available_groups,
        'business_group_choices': business_group_choices_for_api(),
        'personal_currency': personal_currency,
        'primary_currency': primary_currency,
        'top_earners': top_earners,
        'is_admin': is_admin,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sales_performance_report(request):
    """
    Sales Performance Report
    Shows sales by employee, achievement metrics
    """
    from django.db.models import Sum, Count, Avg
    from django.utils.dateparse import parse_date

    user = request.user
    user_profile = None
    try:
        user_profile = UserProfile.objects.get(email=user.email)
        is_admin = user_profile.role.lower() in ['admin', 'administrator']
    except UserProfile.DoesNotExist:
        is_admin = False

    start_date = parse_date(request.query_params.get("start_date") or "")
    end_date = parse_date(request.query_params.get("end_date") or "")

    from .business_groups import (
        apply_business_group_to_orders,
        business_group_choices_for_api,
        currency_for_business_group,
        resolve_dashboard_business_group,
        sales_totals_by_business_group,
    )
    from .permissions import user_is_finance

    can_view_all_groups = is_admin or user_is_finance(request)
    effective_group, view_all_groups, available_groups = resolve_dashboard_business_group(
        request, user_profile, can_view_all_groups
    )

    orders = Order.objects.all()
    org = getattr(request, "organization", None)
    if org:
        orders = filter_queryset_by_organization(orders, org)

    if start_date and end_date:
        orders = orders.filter(order_date__range=[start_date, end_date])
    elif start_date:
        orders = orders.filter(order_date__gte=start_date)
    elif end_date:
        orders = orders.filter(order_date__lte=end_date)

    if not is_admin and not user_is_finance(request):
        possible_employee_ids = []
        if user_profile and user_profile.employee_id:
            possible_employee_ids.append(user_profile.employee_id)
        orders = orders.filter(employee_id__in=possible_employee_ids)

    base_orders = orders
    orders = apply_business_group_to_orders(orders, effective_group)

    from .currencies import active_currency_totals, normalize_currency, primary_currency_from_totals
    from .models import UserProfile as UP

    sales_data = orders.values('employee_id', 'position_name', 'currency').annotate(
        total_sales=Sum('sales_amount'),
        order_count=Count('id'),
        avg_order=Avg('sales_amount'),
    ).order_by('-total_sales')

    total_sales = orders.aggregate(Sum('sales_amount'))['sales_amount__sum'] or 0
    total_orders = orders.count()

    personal_currency = normalize_currency(
        user_profile.personal_currency if user_profile else None
    )
    by_business_group = (
        sales_totals_by_business_group(base_orders) if view_all_groups else []
    )
    if effective_group:
        primary_currency = currency_for_business_group(effective_group, personal_currency)
    else:
        primary_currency = primary_currency_from_totals(
            [
                {"currency": row["currency"], "total": row["total"]}
                for row in by_business_group
            ],
            fallback=personal_currency,
        )
    totals_by_currency = (
        active_currency_totals([{"currency": primary_currency, "total": float(total_sales)}])
        if effective_group
        else active_currency_totals(
            [
                {"currency": row["currency"], "total": row["total"]}
                for row in by_business_group
            ]
        )
    )
    sales_rows = []
    for row in sales_data:
        profile = UP.objects.filter(employee_id=row["employee_id"]).first()
        row_currency = currency_for_business_group(
            profile.business_group if profile else effective_group,
            row.get("currency") or primary_currency,
        )
        sales_rows.append(
            {
                **row,
                "currency": row_currency,
                "business_group": profile.business_group if profile else "",
                "total_sales": float(row["total_sales"] or 0),
                "avg_order": float(row["avg_order"] or 0),
            }
        )

    return Response({
        'total_sales': float(total_sales),
        'total_orders': total_orders,
        'totals_by_currency': totals_by_currency,
        'by_business_group': by_business_group,
        'business_group': effective_group,
        'view_all_business_groups': view_all_groups,
        'available_business_groups': available_groups,
        'business_group_choices': business_group_choices_for_api(),
        'personal_currency': personal_currency,
        'primary_currency': primary_currency,
        'sales_data': sales_rows,
        'start_date': str(start_date) if start_date else None,
        'end_date': str(end_date) if end_date else None,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employee_earnings_report(request):
    """
    Employee Earnings Report
    Detailed breakdown of commissions by employee
    """
    from django.db.models import Sum, Count
    from .list_scope import list_limit_for_request

    user = request.user
    user_profile = None
    try:
        user_profile = UserProfile.objects.get(email=user.email)
        is_admin = user_profile.role.lower() in ['admin', 'administrator']
    except UserProfile.DoesNotExist:
        is_admin = False

    from .business_groups import (
        apply_business_group_to_commissions,
        currency_for_business_group,
        resolve_dashboard_business_group,
    )
    from .permissions import user_is_finance

    can_view_all_groups = is_admin or user_is_finance(request)
    effective_group, _, _ = resolve_dashboard_business_group(
        request, user_profile, can_view_all_groups
    )

    commissions = Commission.objects.all()

    if not is_admin and not user_is_finance(request):
        possible_emails = [user.email]
        if user_profile and user_profile.employee_id:
            possible_emails.append(f"{user_profile.employee_id}@company.com")
        commissions = commissions.filter(employee__email__in=possible_emails)

    commissions = apply_business_group_to_commissions(commissions, effective_group)

    q = (request.query_params.get("q") or "").strip()
    if q and is_admin:
        from .list_scope import commission_employee_search_q
        commissions = commissions.filter(commission_employee_search_q(q))

    earnings_data = commissions.values(
        'employee__name', 'employee__email', 'employee_id'
    ).annotate(
        total_earnings=Sum('commission_amount'),
        commission_count=Count('id'),
        avg_commission=Sum('commission_amount')
    ).order_by('-total_earnings')

    limit = list_limit_for_request(request, searching=bool(q)) if is_admin else None
    total_count = earnings_data.count()
    earnings_list = []
    for row in earnings_data[:limit] if limit else earnings_data:
        profile = UserProfile.objects.filter(email=row.get("employee__email")).first()
        earnings_list.append(
            {
                **row,
                "business_group": profile.business_group if profile else "",
                "currency": currency_for_business_group(
                    profile.business_group if profile else effective_group,
                    profile.personal_currency if profile else None,
                ),
            }
        )

    return Response({
        'earnings': earnings_list,
        'is_admin': is_admin,
        'limited': bool(limit and total_count > limit),
        'count': total_count,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def period_analytics_report(request):
    """
    Period-wise Analytics Report
    Monthly, quarterly, or annual commission totals (respects date filters).
    """
    from django.db.models import Sum, Count
    from django.utils.dateparse import parse_date
    from datetime import date, timedelta
    from dateutil.relativedelta import relativedelta

    from .currencies import active_currency_totals, normalize_currency, primary_currency_from_totals
    from .business_groups import (
        apply_business_group_to_commissions,
        currency_for_business_group,
        resolve_dashboard_business_group,
    )
    from .permissions import user_is_finance

    user = request.user
    user_profile = None
    try:
        user_profile = UserProfile.objects.get(email=user.email)
        is_admin = user_profile.role.lower() in ['admin', 'administrator']
    except UserProfile.DoesNotExist:
        is_admin = False
        user_profile = None

    can_view_all_groups = is_admin or user_is_finance(request)
    effective_group, _, _ = resolve_dashboard_business_group(
        request, user_profile, can_view_all_groups
    )

    period = request.query_params.get('period', 'monthly')
    start_date = parse_date(request.query_params.get("start_date") or "")
    end_date = parse_date(request.query_params.get("end_date") or "")

    if not end_date:
        end_date = date.today()
    if not start_date:
        if period == 'annual':
            start_date = end_date - relativedelta(years=4)
        elif period == 'quarterly':
            start_date = end_date - relativedelta(months=15)
        else:
            start_date = end_date - relativedelta(months=11)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    commissions = Commission.objects.all()
    org = getattr(request, "organization", None)
    if org:
        commissions = commissions.filter(sale__order__organization=org)

    if not is_admin and not user_is_finance(request):
        possible_emails = [user.email]
        if user_profile and user_profile.employee_id:
            possible_emails.append(f"{user_profile.employee_id}@company.com")
        commissions = commissions.filter(employee__email__in=possible_emails)

    commissions = apply_business_group_to_commissions(commissions, effective_group)
    commissions = commissions.filter(
        sale__order__order_date__gte=start_date,
        sale__order__order_date__lte=end_date,
    )

    def quarter_start(value):
        quarter_month = ((value.month - 1) // 3) * 3 + 1
        return date(value.year, quarter_month, 1)

    def iter_buckets():
        if period == 'annual':
            cursor = date(start_date.year, 1, 1)
            while cursor <= end_date:
                bucket_start = max(cursor, start_date)
                bucket_end = min(date(cursor.year, 12, 31), end_date)
                yield bucket_start, bucket_end, str(cursor.year)
                cursor = date(cursor.year + 1, 1, 1)
            return

        if period == 'quarterly':
            cursor = quarter_start(start_date)
            while cursor <= end_date:
                next_quarter = cursor + relativedelta(months=3)
                bucket_start = max(cursor, start_date)
                bucket_end = min(next_quarter - timedelta(days=1), end_date)
                quarter_num = (cursor.month - 1) // 3 + 1
                yield bucket_start, bucket_end, f"Q{quarter_num} {cursor.year}"
                cursor = next_quarter
            return

        cursor = date(start_date.year, start_date.month, 1)
        while cursor <= end_date:
            next_month = cursor + relativedelta(months=1)
            bucket_start = max(cursor, start_date)
            bucket_end = min(next_month - timedelta(days=1), end_date)
            yield bucket_start, bucket_end, cursor.strftime('%b %Y')
            cursor = next_month

    period_data = []
    period_primary_currency = (
        currency_for_business_group(effective_group, user_profile.personal_currency if user_profile else None)
        if effective_group
        else None
    )
    for bucket_start, bucket_end, label in iter_buckets():
        bucket_qs = commissions.filter(
            sale__order__order_date__gte=bucket_start,
            sale__order__order_date__lte=bucket_end,
        )
        if period_primary_currency:
            bucket_total = bucket_qs.aggregate(total=Sum("commission_amount"))["total"] or 0
            totals_by_currency = active_currency_totals(
                [{"currency": period_primary_currency, "total": float(bucket_total)}]
            )
        else:
            totals_by_currency = active_currency_totals(
                [
                    {
                        "currency": normalize_currency(row["sale__order__currency"]),
                        "total": float(row["total"] or 0),
                    }
                    for row in bucket_qs.values("sale__order__currency").annotate(
                        total=Sum("commission_amount")
                    )
                ]
            )
        total = sum(item["total"] for item in totals_by_currency)
        period_data.append({
            'period': label,
            'total': float(total),
            'count': bucket_qs.count(),
            'totals_by_currency': totals_by_currency,
            'currency': (
                totals_by_currency[0]["currency"]
                if len(totals_by_currency) == 1
                else None
            ),
        })

    personal_currency = normalize_currency(
        user_profile.personal_currency if user_profile else None
    )
    if effective_group:
        primary_currency = currency_for_business_group(effective_group, personal_currency)
        overall_totals = active_currency_totals(
            [
                {
                    "currency": primary_currency,
                    "total": float(
                        commissions.aggregate(total=Sum("commission_amount"))["total"] or 0
                    ),
                }
            ]
        )
    else:
        overall_totals = active_currency_totals(
            [
                {
                    "currency": normalize_currency(row["sale__order__currency"]),
                    "total": float(row["total"] or 0),
                }
                for row in commissions.values("sale__order__currency").annotate(
                    total=Sum("commission_amount")
                )
            ]
        )
        primary_currency = primary_currency_from_totals(
            overall_totals, fallback=personal_currency
        )

    return Response({
        'period': period,
        'start_date': str(start_date),
        'end_date': str(end_date),
        'data': period_data,
        'totals_by_currency': overall_totals,
        'business_group': effective_group,
        'personal_currency': personal_currency,
        'primary_currency': primary_currency,
        'is_admin': is_admin,
    })


# =====================================================
# Phase 2: Approvals, payroll export, bulk recalc
# =====================================================

def _commission_queryset_for_export(request):
    """Base queryset for payroll export (admin/finance: all; employee: own)."""
    queryset = Commission.objects.select_related(
        "employee",
        "sale",
        "sale__order",
        "compensation_plan",
    )
    if user_can_view_finance_data(request):
        return queryset
    profile = get_request_user_profile(request)
    if not profile:
        return queryset.none()
    emails = [request.user.email]
    if profile.employee_id:
        emails.append(f"{profile.employee_id}@company.com")
    return queryset.filter(employee__email__in=emails)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approve_commissions_view(request):
    """
    Approve calculated commissions for payroll.

    Body: { "ids": [1,2,3] } and/or { "start_date": "2025-01-01", "end_date": "2025-01-31" }
    """
    require_admin(request)
    ids = request.data.get("ids") or []
    start_date = parse_date(request.data.get("start_date") or "")
    end_date = parse_date(request.data.get("end_date") or "")

    queryset = Commission.objects.filter(status=Commission.STATUS_CALCULATED)
    if ids:
        queryset = queryset.filter(id__in=ids)
    org = getattr(request, "organization", None)
    if org:
        queryset = queryset.filter(sale__order__organization=org)
    if start_date and end_date:
        queryset = queryset.filter(
            sale__order__order_date__range=[start_date, end_date]
        )
    if not ids and not (start_date and end_date):
        return Response(
            {"error": "Provide commission ids and/or start_date + end_date"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    count = approve_commissions(queryset, request.user)
    record_audit(
        request,
        "commissions_approved",
        {
            "approved": count,
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
            "ids": ids,
        },
    )
    return Response({"approved": count})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def commission_payroll_export(request):
    """
    CSV export for payroll (approved commissions by default).

    Query: start_date, end_date, status=approved|calculated|all
    """
    start_date = parse_date(request.query_params.get("start_date") or "")
    end_date = parse_date(request.query_params.get("end_date") or "")
    status_param = (request.query_params.get("status") or "approved").lower()

    queryset = _commission_queryset_for_export(request)
    if start_date and end_date:
        queryset = queryset.filter(
            sale__order__order_date__range=[start_date, end_date]
        )
    if status_param == "approved":
        queryset = queryset.filter(status=Commission.STATUS_APPROVED)
    elif status_param == "manager_approved":
        queryset = queryset.filter(status=Commission.STATUS_MANAGER_APPROVED)
    elif status_param == "paid":
        queryset = queryset.filter(status=Commission.STATUS_PAID)
    elif status_param == "calculated":
        queryset = queryset.filter(status=Commission.STATUS_CALCULATED)
    elif status_param != "all":
        return Response(
            {"error": "status must be approved, manager_approved, paid, calculated, or all"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "commission_id",
        "employee_id",
        "employee_name",
        "employee_email",
        "order_id",
        "order_date",
        "sales_amount",
        "commission_amount",
        "status",
        "plan_name",
        "calculated_at",
        "approved_at",
    ])

    for comm in queryset.order_by("sale__order__order_date", "employee__name"):
        order = comm.sale.order if comm.sale_id and comm.sale.order_id else None
        profile = UserProfile.objects.filter(email=comm.employee.email).first()
        writer.writerow([
            comm.id,
            profile.employee_id if profile else "",
            comm.employee.name,
            comm.employee.email,
            order.order_id if order else "",
            order.order_date.isoformat() if order and order.order_date else "",
            order.sales_amount if order else "",
            comm.commission_amount,
            comm.status,
            comm.compensation_plan.plan_name if comm.compensation_plan_id else "",
            comm.calculated_at.isoformat() if comm.calculated_at else "",
            comm.approved_at.isoformat() if comm.approved_at else "",
        ])

    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="payroll_commissions.csv"'
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def recalculate_commissions_view(request):
    """
    Recalculate commissions for orders in a date range (admin).

    Body: {
      "start_date": "2025-01-01",
      "end_date": "2025-01-31",
      "force": true,
      "q": "adwik22"   // optional — only orders for matching employees
    }
    force=true replaces approved commissions; default skips approved orders.
    """
    require_admin(request)
    start_date = parse_date(request.data.get("start_date") or "")
    end_date = parse_date(request.data.get("end_date") or "")
    if not start_date or not end_date:
        return Response(
            {"error": "start_date and end_date are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    force = bool(request.data.get("force", False))
    employee_q = (request.data.get("q") or "").strip()
    stats = recalculate_orders_in_range(
        start_date,
        end_date,
        force=force,
        organization=getattr(request, "organization", None),
        employee_q=employee_q or None,
    )
    record_audit(
        request,
        "commissions_recalculated",
        {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "force": force,
            "employee_q": employee_q,
            **stats,
        },
    )
    return Response(stats)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_log_list(request):
    """Recent audit events (admin / finance / manager)."""
    if not (user_can_view_finance_data(request) or user_is_manager(request)):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied("Only administrators, finance, or managers can access audit logs")
    limit = min(int(request.query_params.get("limit", 100)), 500)
    logs = AuditLog.objects.select_related("user").order_by("-created_at")
    logs = filter_queryset_by_organization(
        logs, getattr(request, "organization", None)
    )[:limit]
    data = [
        {
            "id": row.id,
            "action": row.action,
            "user_email": row.user_email,
            "detail": row.detail,
            "ip_address": row.ip_address,
            "request_id": row.request_id,
            "created_at": row.created_at.isoformat(),
        }
        for row in logs
    ]
    return Response({"count": len(data), "results": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def import_job_detail(request, job_id):
    """Poll status of a background CSV import."""
    org = getattr(request, "organization", None)
    job = ImportJob.objects.filter(pk=job_id, organization=org).first()
    if not job:
        return Response({"error": "Import job not found"}, status=status.HTTP_404_NOT_FOUND)

    if not user_is_admin(request) and job.created_by_id != request.user.id:
        return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    return Response({
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "source_filename": job.source_filename,
        "row_count": job.row_count,
        "result": job.result,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    })