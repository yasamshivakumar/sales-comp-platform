import csv
import io
import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import validate_email
from django.db.models import Prefetch
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from rest_framework import generics, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .audit import record_audit
from .authentication import issue_user_token, token_expires_at_iso
from .emails import notify_admins, notify_user
from .imports import process_orders_csv, process_users_csv, should_use_async_import
from .invites import accept_invite, get_valid_invite, invite_context
from .models import (
    AuditLog,
    Commission,
    CompensationPlan,
    CompensationTier,
    Employee,
    HierarchyRelationship,
    ImportJob,
    Order,
    Sale,
    SCFlatRateTable,
    SCRateTable,
    UserProfile,
)
from .permissions import (
    get_request_user_profile,
    require_admin,
    require_finance_or_admin,
    user_can_view_finance_data,
    user_is_admin,
    user_is_finance,
    user_is_manager,
)
from .serializers import (
    CommissionSerializer,
    CompensationPlanSerializer,
    CompensationTierSerializer,
    EmployeeSerializer,
    HierarchyRelationshipSerializer,
    OrderSerializer,
    SaleSerializer,
    SCFlatRateTableSerializer,
    SCRateTableSerializer,
    UserProfileSerializer,
)
from .services import (
    approve_commissions,
    calculate_commission_for_order,
    recalculate_orders_in_range,
)
from .tenants import filter_queryset_by_organization, get_profile_for_user

logger = logging.getLogger("commissions")


def _apply_onboarding_password(django_user, user_created):
    """Set initial password only when DEFAULT_ONBOARDING_PASSWORD is configured."""
    pwd = getattr(settings, "DEFAULT_ONBOARDING_PASSWORD", "") or ""
    if user_created and pwd:
        django_user.set_password(pwd)

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer


class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer


class CommissionViewSet(viewsets.ModelViewSet):
    serializer_class = CommissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Q

        from .enterprise_views import _commission_base_queryset, commission_date_q
        from .list_scope import commission_employee_search_q
        from .user_scope import profile_commission_q

        queryset = _commission_base_queryset(self.request)
        profile = get_request_user_profile(self.request)

        if not (
            user_can_view_finance_data(self.request)
            or user_is_manager(self.request)
        ):
            if profile:
                queryset = queryset.filter(
                    profile_commission_q(profile, self.request.user.email)
                )
            else:
                queryset = queryset.filter(
                    employee__email__iexact=self.request.user.email
                )

        org = getattr(self.request, "organization", None)
        if org:
            queryset = queryset.filter(
                Q(organization=org) | Q(sale__order__organization=org)
            ).distinct()

        status_filter = self.request.query_params.get("status")
        if status_filter in {choice[0] for choice in Commission.STATUS_CHOICES}:
            queryset = queryset.filter(status=status_filter)

        start_date = parse_date(self.request.query_params.get("start_date") or "")
        end_date = parse_date(self.request.query_params.get("end_date") or "")
        if start_date and end_date:
            queryset = queryset.filter(commission_date_q(start_date, end_date))

        search = (self.request.query_params.get("q") or "").strip()
        if search:
            queryset = queryset.filter(
                commission_employee_search_q(search, organization=org)
            )

        limit = self.request.query_params.get("limit")
        if limit:
            try:
                queryset = queryset[: int(limit)]
            except (TypeError, ValueError):
                pass

        return queryset.order_by("-calculated_at", "-id")


# ====================================================
# SC Rate Table ViewSet
# ====================================================
class SCRateTableViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SC Rate Table (Tiered Commission Rates)
    
    Endpoints:
    - GET /sc-rate-tables/ - List all rate tables
    - GET /sc-rate-tables/?compensation_plan=<id> - Filter by compensation plan
    - POST /sc-rate-tables/ - Create new rate table
    - GET /sc-rate-tables/<id>/ - Get specific rate table
    - PUT/PATCH /sc-rate-tables/<id>/ - Update rate table
    - DELETE /sc-rate-tables/<id>/ - Delete rate table
    """
    serializer_class = SCRateTableSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = SCRateTable.objects.all().order_by('compensation_plan', 'sequence', 'from_amount')
        
        # Filter by compensation plan if provided
        compensation_plan_id = self.request.query_params.get('compensation_plan', None)
        if compensation_plan_id:
            queryset = queryset.filter(compensation_plan_id=compensation_plan_id)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        return queryset


# ====================================================
# SC Flat Rate Table ViewSet
# ====================================================
class SCFlatRateTableViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SC Flat Rate Table (Fixed Commission Rates)
    
    Endpoints:
    - GET /sc-flat-rate-tables/ - List all flat rate tables
    - GET /sc-flat-rate-tables/?compensation_plan=<id> - Filter by compensation plan
    - POST /sc-flat-rate-tables/ - Create new flat rate table
    - GET /sc-flat-rate-tables/<id>/ - Get specific flat rate table
    - PUT/PATCH /sc-flat-rate-tables/<id>/ - Update flat rate table
    - DELETE /sc-flat-rate-tables/<id>/ - Delete flat rate table
    """
    serializer_class = SCFlatRateTableSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = SCFlatRateTable.objects.all().order_by('compensation_plan')
        
        # Filter by compensation plan if provided
        compensation_plan_id = self.request.query_params.get('compensation_plan', None)
        if compensation_plan_id:
            queryset = queryset.filter(compensation_plan_id=compensation_plan_id)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        return queryset

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


@api_view(["POST"])
@permission_classes([AllowAny])
def book_demo_request(request):
    """Public marketing form endpoint that emails demo requests to the sales inbox."""
    data = request.data or {}
    name = str(data.get("name") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    company = str(data.get("company") or "").strip()
    phone = str(data.get("phone") or "").strip()
    message = str(data.get("message") or "").strip()

    if not name:
        return Response({"error": "Name is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not email:
        return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        validate_email(email)
    except ValidationError:
        return Response({"error": "Enter a valid email address."}, status=status.HTTP_400_BAD_REQUEST)

    recipient = getattr(settings, "DEMO_REQUEST_EMAIL", "shivakumar@incentra.co.in")
    subject = f"[Incentra] Demo request from {name}"
    body = (
        "New demo request from the Incentra marketing website.\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Company: {company or 'Not provided'}\n"
        f"Phone: {phone or 'Not provided'}\n\n"
        f"Message:\n{message or 'Not provided'}\n"
    )
    sent = notify_user(recipient, subject, body)
    if not sent:
        return Response(
            {
                "error": "Email service is temporarily unavailable. Please contact us directly.",
                "contact_email": recipient,
                "contact_phone": "8499087617",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response({"message": "Demo request sent successfully."})


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def invite_detail(request, token):
    invite = get_valid_invite(token)
    if not invite:
        return Response(
            {"error": "Invite is invalid, expired, or already used."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(invite_context(invite))


invite_detail.throttle_scope = "login"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def invite_accept(request, token):
    password = request.data.get("password") or ""
    confirm_password = request.data.get("confirm_password") or password
    if len(password) < 8:
        return Response(
            {"error": "Password must be at least 8 characters."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if password != confirm_password:
        return Response(
            {"error": "Password and confirmation do not match."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = accept_invite(token, password)
    if not user:
        return Response(
            {"error": "Invite is invalid, expired, or already used."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    record_audit(
        request,
        "invite_accepted",
        {"email": user.email, "user_id": user.id},
    )
    return Response({"message": "Password set successfully. You can now sign in."})


invite_accept.throttle_scope = "login"


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def login(request):
    username = request.data.get('username')
    password = request.data.get('password')

    # Authenticate user
    user = authenticate(
        username=username,
        password=password
    )

    if not user:
        record_audit(request, "login_failed", {"username": username})
        return Response(
            {'error': 'Invalid credentials'},
            status=400
        )

    # Get or create token
    token = issue_user_token(user)
    record_audit(request, "login_success", {"user_id": user.pk})

    # Return success response
    return Response({
        'message': 'Login successful',
        'token': token.key,
        'username': user.username
    })

class CompensationPlanListCreateView(generics.ListCreateAPIView):
    serializer_class = CompensationPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = CompensationPlan.objects.all().order_by("-created_at")
        return filter_queryset_by_organization(
            qs, getattr(self.request, "organization", None)
        )

    def perform_create(self, serializer):
        serializer.save(organization=getattr(self.request, "organization", None))

    def check_admin_permission(self, request):
        """Check if user is admin, raise PermissionDenied if not"""
        try:
            user_profile = UserProfile.objects.get(email=request.user.email)
            is_admin = user_profile.role.lower() in ['admin', 'administrator']
            if not is_admin:
                raise PermissionDenied("Only administrators can access compensation plans")
        except UserProfile.DoesNotExist:
            raise PermissionDenied("User profile not found")
        return True

    def list(self, request, *args, **kwargs):
        """Only admins can view compensation plans"""
        self.check_admin_permission(request)
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Only admins can create compensation plans"""
        self.check_admin_permission(request)
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Only admins can delete compensation plans"""
        self.check_admin_permission(request)
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Only admins can update compensation plans"""
        self.check_admin_permission(request)
        return super().update(request, *args, **kwargs)


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

            # ---------------------------------------------------
            # Create / Update UserProfile
            # ---------------------------------------------------
            org = getattr(request, "organization", None)
            lookup = {"email": email}
            if org:
                lookup["organization"] = org

            profile, created = UserProfile.objects.update_or_create(
                **lookup,
                defaults={
                    "organization": org,
                    # User
                    'enable_login': enable_login,
                    'name': str(
                        data.get('name', '')
                    ).strip(),

                    'role': str(
                        data.get('role', 'Sales Rep')
                    ).strip(),

                    # People
                    'username': username,

                    'first_name': str(
                        data.get('first_name', '')
                    ).strip(),

                    'last_name': str(
                        data.get('last_name', '')
                    ).strip(),

                    'prefix': str(
                        data.get('prefix', '')
                    ).strip(),

                    'employee_id': str(
                        data.get('employee_id', '')
                    ).strip(),

                    'hire_date': data.get('hire_date'),

                    'personal_target': personal_target,

                    'personal_currency': str(
                        data.get('personal_currency', 'INR')
                    ).strip(),

                    'business_group': str(
                        data.get('business_group', 'India')
                    ).strip(),

                    # Title
                    'title': str(
                        data.get('title', '')
                    ).strip(),

                    'pay_period_type': str(
                        data.get('pay_period_type', 'Monthly')
                    ).strip(),

                    # Position
                    'position_name': str(
                        data.get('position_name', '')
                    ).strip(),

                    'position_title': str(
                        data.get('position_title', '')
                    ).strip(),
                }
            )

            # ---------------------------------------------------
            # Login / activation invite
            # ---------------------------------------------------
            invite_status = "none"
            invite_link = ""
            invite_error = ""

            if enable_login:
                if created:
                    from .invites import build_invite_url, create_user_invite

                    _, token, sent, invite_error = create_user_invite(
                        profile,
                        invited_by=request.user,
                    )
                    invite_status = "sent" if sent else "created"
                    if token and not sent:
                        invite_link = build_invite_url(token)
                else:
                    from .auth_utils import provision_login_user

                    provision_login_user(profile)
                    invite_status = "existing"

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
            payload = dict(serializer.data)
            payload["invite_status"] = invite_status
            if invite_link:
                payload["invite_link"] = invite_link
            if invite_error:
                payload["invite_error"] = invite_error

            return Response(
                payload,
                status=status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
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

    def post(self, request):
        if "file" not in request.FILES:
            return Response(
                {"error": "No file uploaded"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_file = request.FILES["file"]
        if not uploaded_file.name.lower().endswith(".csv"):
            return Response(
                {"error": "Only CSV files are supported"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization = getattr(request, "organization", None)
        if not organization:
            return Response(
                {"error": "Organization context missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            decoded_file = uploaded_file.read().decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(decoded_file)))
        except Exception as exc:
            return Response(
                {"error": f"Error reading CSV file: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if should_use_async_import(len(rows)):
            from .tasks import process_import_job_task

            job = ImportJob.objects.create(
                organization=organization,
                created_by=request.user,
                job_type=ImportJob.JOB_USERS,
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
                "user_setup_upload_queued",
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

        result = process_users_csv(organization, decoded_file)
        payload = {
            "message": "Upload completed successfully",
            **result,
        }
        record_audit(
            request,
            "user_setup_upload",
            {
                "success": result["success"],
                "failed": result["failed"],
                "filename": uploaded_file.name,
            },
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


def _orders_queryset_for_request(request):
    """Orders visible to the user, with commission data prefetched."""
    from .list_scope import order_search_q

    org = getattr(request, "organization", None)
    queryset = filter_queryset_by_organization(
        Order.objects.select_related("sale_record")
        .prefetch_related(
            Prefetch(
                "sale_record__commission_set",
                queryset=filter_queryset_by_organization(
                    Commission.objects.order_by("id"),
                    org,
                ),
            )
        )
        .order_by("-order_date", "-id"),
        org,
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
        user_profile = get_profile_for_user(
            user,
            organization=getattr(request, "organization", None),
        )
        if not user_profile:
            raise UserProfile.DoesNotExist
        is_admin = user_profile.role.lower() in ["admin", "administrator"]
        if is_admin:
            return queryset
        if user_profile.employee_id:
            return queryset.filter(employee_id=user_profile.employee_id)
        return queryset.filter(employee_email=user.email)
    except UserProfile.DoesNotExist:
        return queryset.none()


class OrderListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/orders/   -> List orders (role-scoped; supports order_status and q)
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
    """GET/PATCH /api/orders/<id>/ — updates recalculate commission when eligible."""
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
            "IncentivePro: order upload finished",
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


signup.throttle_scope = "login"
login.throttle_scope = "login"


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
    
    try:
        # Try to get user by email field first
        user = User.objects.get(email=email)
        
    except User.DoesNotExist:
        # Fallback: try to get user by username (which might be email)
        try:
            user = User.objects.get(username=email)
        except User.DoesNotExist:
            logger.warning("Login attempt with non-existent email: %s", email)
            record_audit(request, "login_failed", {"email": email})
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
    
    # Check password
    if not user.check_password(password):
        logger.warning("Failed login attempt for email: %s", email)
        record_audit(request, "login_failed", {"email": email})
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Check if user is active
    if not user.is_active:
        return Response(
            {'error': 'User account is inactive'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Get or create token
        token = issue_user_token(user)
        
        # Get user profile for additional info
        user_profile = UserProfile.objects.filter(email=user.email).first()
        
        logger.info("Successful login for email: %s", email)
        record_audit(request, "login_success", {"user_id": user.id, "email": email})
        
        return Response({
            'message': 'Login successful',
            'token': token.key,
            'email': user.email,
            'user_id': user.id,
            'role': user_profile.role if user_profile else 'Sales Rep',
            'name': user_profile.name if user_profile else user.get_full_name() or user.username,
            'token_expires_at': token_expires_at_iso(token),
        })
        
    except Exception as e:
        logger.error("Login error: %s", e)
        return Response(
            {'error': 'An error occurred during login'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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
            logger.warning("Failed password change attempt for user: %s", user.email)
            return Response(
                {'error': 'Old password is incorrect'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        # Create new token for current session
        token = issue_user_token(user)
        
        logger.info("Password changed successfully for user: %s", user.email)
        
        return Response({
            'message': 'Password changed successfully',
            'token': token.key,
            'token_expires_at': token_expires_at_iso(token),
        })
        
    except Exception as e:
        logger.error("Password change error: %s", e)
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
            'employee_id': user_profile.employee_id,
            'organization_slug': org.slug if org else None,
            'organization_name': org.name if org else None,
        })
        
    except UserProfile.DoesNotExist:
        return Response(
            {'error': 'User profile not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error("Error fetching user profile: %s", e)
        return Response(
            {'error': 'An error occurred'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =====================================================
# REPORTS API
# =====================================================

def _profile_display_name(profile):
    if not profile:
        return ""
    full = f"{profile.first_name} {profile.last_name}".strip()
    return full or (profile.name or "").strip() or profile.email


def _manager_for_profile(profile, organization=None):
    qs = HierarchyRelationship.objects.filter(
        child_participant=profile,
    ).select_related("parent_participant")
    if organization:
        qs = qs.filter(
            parent_participant__organization=organization,
            child_participant__organization=organization,
        )
    rel = qs.first()
    return rel.parent_participant if rel else None


def serialize_user_profile_detail(profile, *, organization=None):
    """Full imported employee profile for order forms and admin views."""
    manager = _manager_for_profile(profile, organization)
    territory = profile.territory
    return {
        "id": profile.id,
        "employee_id": profile.employee_id or "",
        "display_name": _profile_display_name(profile),
        "name": profile.name or "",
        "email": profile.email or "",
        "role": profile.role or "",
        "username": profile.username or "",
        "first_name": profile.first_name or "",
        "last_name": profile.last_name or "",
        "prefix": profile.prefix or "",
        "title": profile.title or "",
        "position_name": profile.position_name or "",
        "position_title": profile.position_title or "",
        "pay_period_type": profile.pay_period_type or "",
        "business_group": profile.business_group or "",
        "personal_target": str(profile.personal_target),
        "personal_currency": profile.personal_currency or "",
        "hire_date": profile.hire_date.isoformat() if profile.hire_date else "",
        "territory_id": profile.territory_id,
        "territory_name": territory.name if territory else "",
        "territory_code": territory.code if territory else "",
        "manager_name": _profile_display_name(manager) if manager else "",
        "manager_employee_id": manager.employee_id if manager else "",
        "hierarchy": profile.hierarchy or "",
        "function_name": profile.function_name or "",
        "title_category": profile.title_category or "",
        "level": profile.level or "",
        "market": profile.market or "",
        "region": profile.market or "",
        "enable_login": profile.enable_login,
        "crm_user_id": profile.crm_user_id or "",
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_user_detail(request, pk):
    """Return full imported employee profile for Create Order auto-fill."""
    org = getattr(request, "organization", None)
    profile = filter_queryset_by_organization(
        UserProfile.objects.select_related("territory"),
        org,
    ).filter(pk=pk).first()
    if not profile:
        return Response(
            {"error": "Employee profile not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(serialize_user_profile_detail(profile, organization=org))


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
        ).filter(
            parent_participant__organization=org,
            child_participant__organization=org,
        ).select_related("parent_participant"):
            manager_by_child[rel.child_participant_id] = rel.parent_participant

    results = []
    for profile in profile_list:
        manager = manager_by_child.get(profile.id)
        detail = serialize_user_profile_detail(profile, organization=org)
        detail["manager_name"] = _profile_display_name(manager) if manager else ""
        detail["manager_employee_id"] = manager.employee_id if manager else ""
        results.append(detail)

    return Response(results)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def commission_summary_report(request):
    """
    Commission Summary Report
    Shows total commissions, top earners, metrics
    Admin: All employees, Employee: Own only
    """
    from django.db.models import Sum, Count, Avg
    from .currencies import active_currency_totals, normalize_currency
    from .enterprise_views import (
        _apply_commission_filters,
        _commission_base_queryset,
        with_commission_currency,
    )
    from .user_scope import profile_commission_q

    queryset = _commission_base_queryset(request)
    profile = get_request_user_profile(request)
    if not (user_can_view_finance_data(request) or user_is_admin(request)):
        if profile:
            queryset = queryset.filter(profile_commission_q(profile, request.user.email))
        else:
            queryset = queryset.none()

    queryset, start_date, end_date = _apply_commission_filters(queryset, request)
    queryset = with_commission_currency(queryset)

    totals_rows = list(
        queryset.values("report_currency").annotate(
            total=Sum("commission_amount"),
            count=Count("id"),
        )
    )
    commission_totals = [
        {
            "currency": normalize_currency(row["report_currency"]),
            "total": float(row["total"] or 0),
            "count": row["count"],
        }
        for row in totals_rows
    ]
    totals_by_currency = active_currency_totals(commission_totals)
    total_commission = sum(item["total"] for item in totals_by_currency)

    payout_record_count = queryset.count()
    active_reps_count = (
        queryset.filter(sale__order__employee_id__isnull=False)
        .values("sale__order__employee_id")
        .distinct()
        .count()
    )
    if active_reps_count == 0:
        active_reps_count = queryset.values("employee_id").distinct().count()

    avg_commission = queryset.aggregate(Avg("commission_amount"))["commission_amount__avg"] or 0

    top_earners = []
    if user_is_admin(request) or user_can_view_finance_data(request):
        top_earners = list(
            queryset.values("employee__name", "employee__email").annotate(
                total=Sum("commission_amount"),
                count=Count("id"),
            ).order_by("-total")[:5]
        )

    return Response({
        "total_commission": float(total_commission),
        "total_count": payout_record_count,
        "payout_record_count": payout_record_count,
        "active_reps_count": active_reps_count,
        "avg_commission": float(avg_commission),
        "top_earners": top_earners,
        "totals_by_currency": totals_by_currency,
        "is_admin": user_is_admin(request),
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sales_performance_report(request):
    """
    Sales Performance Report
    Shows sales by employee, achievement metrics
    """
    from django.db.models import Sum, Count
    from .business_groups import apply_business_group_to_orders, resolve_dashboard_business_group
    from .currencies import active_currency_totals, normalize_currency

    profile = get_request_user_profile(request)
    is_admin = user_is_admin(request) or user_can_view_finance_data(request)

    orders = filter_queryset_by_organization(
        Order.objects.all(),
        getattr(request, "organization", None),
    )

    start_date = parse_date(request.query_params.get("start_date") or "")
    end_date = parse_date(request.query_params.get("end_date") or "")
    if start_date and end_date:
        orders = orders.filter(order_date__range=[start_date, end_date])

    if not is_admin:
        possible_employee_ids = []
        if profile and profile.employee_id:
            possible_employee_ids.append(profile.employee_id)
        orders = orders.filter(employee_id__in=possible_employee_ids)

    can_view_all_groups = user_is_admin(request) or user_is_finance(request)
    effective_group, _, _ = resolve_dashboard_business_group(
        request, profile, can_view_all_groups
    )
    orders = apply_business_group_to_orders(
        orders,
        effective_group,
        organization=getattr(request, "organization", None),
    )

    sales_data = list(
        orders.values("employee_id", "position_name").annotate(
            total_sales=Sum("sales_amount"),
            order_count=Count("id"),
            avg_order=Sum("sales_amount"),
        ).order_by("-total_sales")
    )

    currency_rows = list(
        orders.values("currency").annotate(
            total=Sum("sales_amount"),
            count=Count("id"),
        )
    )
    totals_by_currency = active_currency_totals(
        [
            {
                "currency": normalize_currency(row["currency"]),
                "total": float(row["total"] or 0),
                "count": row["count"],
            }
            for row in currency_rows
        ]
    )
    total_sales = sum(item["total"] for item in totals_by_currency)
    total_orders = orders.count()

    return Response({
        "total_sales": float(total_sales),
        "total_orders": total_orders,
        "sales_data": sales_data,
        "totals_by_currency": totals_by_currency,
        "is_admin": is_admin,
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employee_earnings_report(request):
    """
    Employee Earnings Report
    Detailed breakdown of commissions by employee
    """
    from django.db.models import Avg, Count, Sum

    user_profile = get_profile_for_user(request.user)
    role = (getattr(user_profile, "role", None) or "").lower()
    is_admin = role in ("admin", "administrator")

    commissions = Commission.objects.all()
    commissions = filter_queryset_by_organization(
        commissions, getattr(request, "organization", None)
    )

    if not is_admin:
        possible_emails = [request.user.email]
        employee_id = getattr(user_profile, "employee_id", None)
        if employee_id:
            possible_emails.append(f"{employee_id}@company.com")
        commissions = commissions.filter(employee__email__in=possible_emails)

    earnings_data = commissions.values(
        "employee__name", "employee__email", "employee_id"
    ).annotate(
        total_earnings=Sum("commission_amount"),
        commission_count=Count("id"),
        avg_commission=Avg("commission_amount"),
    ).order_by("-total_earnings")

    return Response({
        "earnings": list(earnings_data),
        "is_admin": is_admin,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def period_analytics_report(request):
    """
    Period-wise Analytics Report
    Monthly, Quarterly, Annual metrics
    """
    from datetime import date, timedelta

    from dateutil.relativedelta import relativedelta
    from django.db.models import Count, Sum

    from .currencies import active_currency_totals, normalize_currency
    from .enterprise_views import (
        _apply_commission_filters,
        _commission_base_queryset,
        _commissions_for_user,
        commission_date_q,
        with_commission_currency,
    )

    queryset = _commission_base_queryset(request)
    if not (user_can_view_finance_data(request) or user_is_admin(request)):
        queryset = _commissions_for_user(request)

    queryset, start_date, end_date = _apply_commission_filters(queryset, request)
    queryset = with_commission_currency(queryset)

    period = request.query_params.get("period", "monthly")
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=365)

    period_data = []
    cursor = start_date.replace(day=1)

    while cursor <= end_date:
        if period == "quarterly":
            quarter = (cursor.month - 1) // 3
            bucket_start = date(cursor.year, quarter * 3 + 1, 1)
            bucket_end = bucket_start + relativedelta(months=3) - timedelta(days=1)
            label = f"Q{quarter + 1} {cursor.year}"
            cursor = bucket_start + relativedelta(months=3)
        elif period == "annual":
            bucket_start = date(cursor.year, 1, 1)
            bucket_end = date(cursor.year, 12, 31)
            label = str(cursor.year)
            cursor = date(cursor.year + 1, 1, 1)
        else:
            bucket_start = cursor
            bucket_end = (cursor + relativedelta(months=1)) - timedelta(days=1)
            label = cursor.strftime("%B %Y")
            cursor = cursor + relativedelta(months=1)

        if bucket_end < start_date or bucket_start > end_date:
            continue

        scoped = queryset.filter(commission_date_q(bucket_start, bucket_end))
        totals_rows = scoped.values("report_currency").annotate(
            total=Sum("commission_amount"),
            count=Count("id"),
        )
        bucket_total = sum(float(row["total"] or 0) for row in totals_rows)
        bucket_count = sum(row["count"] for row in totals_rows)
        period_data.append(
            {
                "period": label,
                "total": bucket_total,
                "count": bucket_count,
            }
        )

    totals_rows = list(
        queryset.values("report_currency").annotate(
            total=Sum("commission_amount"),
            count=Count("id"),
        )
    )
    totals_by_currency = active_currency_totals(
        [
            {
                "currency": normalize_currency(row["report_currency"]),
                "total": float(row["total"] or 0),
                "count": row["count"],
            }
            for row in totals_rows
        ]
    )

    return Response(
        {
            "period": period,
            "data": period_data,
            "totals_by_currency": totals_by_currency,
            "is_admin": user_is_admin(request),
            "start_date": str(start_date),
            "end_date": str(end_date),
        }
    )


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
    from django.db.models import Q

    from .enterprise_views import commission_date_q

    require_admin(request)
    ids = request.data.get("ids") or []
    start_date = parse_date(request.data.get("start_date") or "")
    end_date = parse_date(request.data.get("end_date") or "")

    queryset = Commission.objects.filter(status=Commission.STATUS_CALCULATED)
    if ids:
        queryset = queryset.filter(id__in=ids)
    org = getattr(request, "organization", None)
    if org:
        queryset = queryset.filter(
            Q(organization=org) | Q(sale__order__organization=org)
        ).distinct()
    if start_date and end_date:
        queryset = queryset.filter(commission_date_q(start_date, end_date))
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
    from .enterprise_views import commission_date_q

    start_date = parse_date(request.query_params.get("start_date") or "")
    end_date = parse_date(request.query_params.get("end_date") or "")
    status_param = (request.query_params.get("status") or "approved").lower()

    queryset = _commission_queryset_for_export(request)
    if start_date and end_date:
        queryset = queryset.filter(commission_date_q(start_date, end_date))
    if status_param == "approved":
        queryset = queryset.filter(status=Commission.STATUS_APPROVED)
    elif status_param == "calculated":
        queryset = queryset.filter(status=Commission.STATUS_CALCULATED)
    elif status_param != "all":
        return Response(
            {"error": "status must be approved, calculated, or all"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    commissions = list(
        queryset.select_related(
            "sale__order",
            "employee",
            "compensation_plan",
        ).order_by("sale__order__order_date", "employee__name")
    )
    emails = [
        comm.employee.email
        for comm in commissions
        if getattr(comm.employee, "email", None)
    ]
    profile_qs = UserProfile.objects.filter(email__in=emails).only("email", "employee_id")
    org = getattr(request, "organization", None)
    if org is not None:
        profile_qs = profile_qs.filter(organization=org)
    profiles_by_email = {
        (profile.email or "").lower(): profile for profile in profile_qs
    }

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

    for comm in commissions:
        order = comm.sale.order if comm.sale_id and comm.sale.order_id else None
        profile = profiles_by_email.get((comm.employee.email or "").lower())
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

    Body: { "start_date": "2025-01-01", "end_date": "2025-01-31", "force": true }
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
    stats = recalculate_orders_in_range(
        start_date,
        end_date,
        force=force,
        organization=getattr(request, "organization", None),
    )
    record_audit(
        request,
        "commissions_recalculated",
        {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "force": force,
            **stats,
        },
    )
    return Response(stats)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_log_list(request):
    """Recent audit events (admin / finance)."""
    require_finance_or_admin(request)
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


email_login.throttle_scope = "login"


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