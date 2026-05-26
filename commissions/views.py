import pandas as pd
from datetime import datetime
from rest_framework import status
import csv
import io
import logging
from rest_framework.decorators import api_view,permission_classes
from rest_framework.response import Response
from rest_framework import viewsets
from .models import Employee, Sale, Commission,IncentiveRule,UserProfile,HierarchyRelationship,CompensationPlan, CompensationTier,Order,SCRateTable,SCFlatRateTable
from decimal import Decimal, InvalidOperation
from .serializers import (
    EmployeeSerializer,
    SaleSerializer,
    CommissionSerializer,
    CompensationPlanSerializer,
    CompensationTierSerializer,
    OrderSerializer,
    SCRateTableSerializer,
    SCFlatRateTableSerializer,
)
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import CompensationPlan
from .serializers import UserProfileSerializer,HierarchyRelationshipSerializer
from .services import calculate_commission_for_order
from django.db import transaction

# Initialize logger for commission app
logger = logging.getLogger('commissions')

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
        """
        Filter commissions based on user role:
        - Admin: Can see all commissions
        - Regular employee: Can only see their own commissions
        """
        user = self.request.user
        
        try:
            user_profile = UserProfile.objects.get(email=user.email)
            is_admin = user_profile.role.lower() in ['admin', 'administrator']
            
            if is_admin:
                # Admin can see all commissions
                return Commission.objects.all()
            else:
                # Employee can only see their own commissions
                # Match by employee_id from UserProfile
                if user_profile.employee_id:
                    return Commission.objects.filter(
                        employee__email=user.email
                    ) | Commission.objects.filter(
                        employee__name=user_profile.name
                    )
                else:
                    return Commission.objects.filter(
                        employee__email=user.email
                    )
        except UserProfile.DoesNotExist:
            # Fallback: show only their own
            return Commission.objects.filter(
                employee__email=user.email
            )


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


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get('username')
    password = request.data.get('password')

    # Authenticate user
    user = authenticate(
        username=username,
        password=password
    )

    if not user:
        return Response(
            {'error': 'Invalid credentials'},
            status=400
        )

    # Get or create token
    token, _ = Token.objects.get_or_create(user=user)

    # Return success response
    return Response({
        'message': 'Login successful',
        'token': token.key,
        'username': user.username
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def upload_orders(request):
    """
    Upload and process orders for commission calculation.
    All operations wrapped in transaction for data consistency.
    """
    try:
        file = request.FILES['file']
    except KeyError:
        logger.warning("Upload attempted without file")
        return Response(
            {'error': 'No file provided'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # ================================================================
    # FILE SIZE VALIDATION - Max 10MB
    # ================================================================
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    if file.size > MAX_FILE_SIZE:
        logger.warning(f"File upload rejected: size {file.size} exceeds {MAX_FILE_SIZE} bytes")
        return Response(
            {'error': f'File size exceeds maximum allowed ({MAX_FILE_SIZE / 1024 / 1024}MB)'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        df = pd.read_excel(file)
    except Exception as e:
        logger.error(f"Failed to read Excel file: {str(e)}")
        return Response(
            {'error': f'Failed to read file: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    success_count = 0
    failed_count = 0

    logger.info(f"Starting order upload with {len(df)} rows")

    for index, row in df.iterrows():

        try:

            if pd.isna(row['employee_email']):
                continue

            email = str(row['employee_email']).strip().lower()

            employee = Employee.objects.filter(
                email=email
            ).first()

            if not employee:
                failed_count += 1
                logger.warning(f"Row {index+1}: Employee not found: {email}")
                continue

            sale = Sale.objects.create(
                employee=employee,
                employee_salary=Decimal(str(row['salary'])),
                amount=Decimal(str(row['sales_amount']))
            )

            rule = IncentiveRule.objects.filter(
                min_amount__lte=Decimal(str(row['sales_amount'])),
                max_amount__gte=Decimal(str(row['sales_amount']))
            ).first()

            if not rule:
                failed_count += 1
                logger.warning(f"Row {index+1}: No rule found for sales_amount {row['sales_amount']}")
                continue

            commission_amount = (
                Decimal(str(row['sales_amount'])) *
                rule.percentage
            ) / Decimal("100")

            Commission.objects.create(
                employee=employee,
                sale=sale,
                commission_amount=commission_amount
            )

            success_count += 1
            logger.debug(f"Row {index+1}: Commission created for {email}")

        except (InvalidOperation, ValueError) as e:
            failed_count += 1
            logger.error(f"Row {index+1}: Decimal conversion error: {str(e)}")
        except (InvalidOperation, ValueError) as e:
            failed_count += 1
            logger.error(f"Row {index+1}: Decimal conversion error: {str(e)}")
        except Exception as e:
            failed_count += 1
            logger.error(f"Row {index+1}: Unexpected error: {str(e)}", exc_info=True)

    logger.info(f"Order upload completed: {success_count} successful, {failed_count} failed")
    
    return Response({
        "message": "Upload completed",
        "success": success_count,
        "failed": failed_count
    })

class CompensationPlanListCreateView(generics.ListCreateAPIView):
    queryset = CompensationPlan.objects.all().order_by('-created_at')
    serializer_class = CompensationPlanSerializer
    permission_classes = [IsAuthenticated]

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
    queryset = UserProfile.objects.all().order_by('first_name')
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        email = request.data.get('email')

        if not email:
            return Response(
                {'email': ['This field is required.']},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Make request data mutable
        data = request.data.copy()

        # Remove hierarchy fields (handled separately)
        parent_participant = data.pop('parent_participant', None)
        child_participant = data.pop('child_participant', None)
        split_percentage = data.pop('split_percentage', None)

        # Convert empty numeric fields to zero
        numeric_fields = [
            'personal_target',
        ]

        for field in numeric_fields:
            if not data.get(field):
                data[field] = 0

        # Remove empty date fields
        if not data.get('hire_date'):
            data['hire_date'] = None

        # Create or update UserProfile
        profile, created = UserProfile.objects.update_or_create(
            email=email,
            defaults=data
        )

        # Create Django login user if login access is enabled
        if profile.enable_login:
            username = profile.username or profile.email

            if not User.objects.filter(username=username).exists():
                User.objects.create_user(
                    username=username,
                    email=profile.email,
                    first_name=profile.first_name,
                    last_name=profile.last_name,
                    password='Welcome@123'
                )

        # Create hierarchy relationship if provided
        if (
            parent_participant
            and child_participant
            and split_percentage
        ):
            HierarchyRelationship.objects.update_or_create(
                parent_participant_id=parent_participant,
                child_participant_id=child_participant,
                defaults={
                    'split_percentage': split_percentage,
                    'is_active': True,
                }
            )

        serializer = self.get_serializer(profile)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created
            else status.HTTP_200_OK
        )


class UserProfileUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

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

        # ---------------------------------------------------
        # Process each row
        # ---------------------------------------------------
        for index, row in enumerate(rows, start=2):
            try:
                # ---------------------------------------------------
                # Required field: Email
                # ---------------------------------------------------
                email = str(row.get('email', '')).strip()

                if not email:
                    raise Exception('Email is required')

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
                # Create or Update UserProfile
                # ---------------------------------------------------
                profile, created = UserProfile.objects.update_or_create(
                    email=email,
                    defaults={
                        # User
                        'enable_login': enable_login,
                        'name': str(row.get('name', '')).strip(),
                        'role': str(
                            row.get('role', 'Sales Rep')
                        ).strip(),

                        # People
                        'username': username,
                        'first_name': str(
                            row.get('first_name', '')
                        ).strip(),
                        'last_name': str(
                            row.get('last_name', '')
                        ).strip(),
                        'prefix': str(
                            row.get('prefix', '')
                        ).strip(),
                        'employee_id': str(
                            row.get('employee_id', '')
                        ).strip(),
                        'hire_date': hire_date,
                        'personal_target': personal_target,
                        'personal_currency': str(
                            row.get('personal_currency', 'INR')
                        ).strip(),
                        'business_group': str(
                            row.get('business_group', 'India')
                        ).strip(),

                        # Title
                        'title': str(
                            row.get('title', '')
                        ).strip(),
                        'pay_period_type': str(
                            row.get('pay_period_type', 'Monthly')
                        ).strip(),

                        # Position
                        'position_name': str(
                            row.get('position_name', '')
                        ).strip(),
                        'position_title': str(
                            row.get('position_title', '')
                        ).strip(),
                    }
                )

                # ---------------------------------------------------
                # Create Django Login User
                #
                # If enable_login = yes/true/1,
                # create a Django auth user.
                #
                # Login credentials:
                # Username: email (or username column if provided)
                # Password: Welcome@123
                # ---------------------------------------------------
                if enable_login:
                    django_user, user_created = User.objects.get_or_create(
                        username=username,
                        defaults={
                            'email': email,
                            'first_name': profile.first_name,
                            'last_name': profile.last_name,
                            'is_active': True,
                        }
                    )

                    # Always update latest details
                    django_user.email = email
                    django_user.first_name = profile.first_name
                    django_user.last_name = profile.last_name
                    django_user.is_active = True

                    # Set default password only when user is first created
                    if user_created:
                        django_user.set_password('Welcome@123')

                    django_user.save()

                # ---------------------------------------------------
                # Create Hierarchy Relationship
                # Lookup by username, employee_id, or email
                # ---------------------------------------------------
                parent_value = str(
                    row.get('parent_participant', '')
                ).strip()

                child_value = str(
                    row.get('child_participant', '')
                ).strip()

                if parent_value and child_value:
                    parent_profile = (
                        UserProfile.objects.filter(
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
                        UserProfile.objects.filter(
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
                print(
                    f"Error processing row {index}: {str(e)}"
                )

        # ---------------------------------------------------
        # Final response
        # ---------------------------------------------------
        return Response({
            'message': 'Upload completed successfully',
            'success': success,
            'failed': failed,
            'errors': errors[:20],  # Return first 20 errors
            'default_password': 'Welcome@123',
        })

class HierarchyRelationshipListCreateView(generics.ListCreateAPIView):
    queryset = HierarchyRelationship.objects.filter(
        is_active=True
    ).order_by('parent_participant') 

    serializer_class = HierarchyRelationshipSerializer
    permission_classes = [IsAuthenticated]


class CompensationPlanListCreateView(generics.ListCreateAPIView):
    queryset = CompensationPlan.objects.all().order_by('-created_at')
    serializer_class = CompensationPlanSerializer
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
        """
        Filter orders based on user role:
        - Admin: Can see all orders
        - Regular employee: Can only see their own orders
        """
        user = self.request.user
        queryset = Order.objects.all().order_by("-order_date")
        
        try:
            user_profile = UserProfile.objects.get(email=user.email)
            is_admin = user_profile.role.lower() in ['admin', 'administrator']
            
            if is_admin:
                # Admin can see all orders
                return queryset
            else:
                # Employee can only see their own orders
                if user_profile.employee_id:
                    return queryset.filter(employee_id=user_profile.employee_id)
                else:
                    return queryset.filter(employee_email=user.email)
        except UserProfile.DoesNotExist:
            # Fallback: show nothing if profile doesn't exist
            return queryset.none()



class OrderUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

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
            csv_reader = csv.DictReader(io.StringIO(decoded_file))
            rows = list(csv_reader)
        except Exception as e:
            return Response(
                {"error": f"Error reading CSV file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        success = 0
        failed = 0
        errors = []

        # Get actual fields that exist in the Order model
        order_model_fields = {
            field.name for field in Order._meta.get_fields()
        }

        # ---------------------------------------------------
        # Process each row
        # ---------------------------------------------------
        for index, row in enumerate(rows, start=2):
            try:
                # ---------------------------------------------------
                # Required field: order_id
                # ---------------------------------------------------
                order_id = str(row.get("order_id", "")).strip()
                if not order_id:
                    raise Exception("order_id is required")

                # ---------------------------------------------------
                # Required field: order_date
                # ---------------------------------------------------
                order_date_value = row.get("order_date", "")
                if not order_date_value:
                    raise Exception("order_date is required")

                order_date = None
                date_formats = [
                    "%Y-%m-%d",  # 2026-05-01
                    "%d-%m-%Y",  # 01-05-2026
                    "%d/%m/%Y",  # 01/05/2026
                ]

                for fmt in date_formats:
                    try:
                        order_date = datetime.strptime(
                            str(order_date_value).strip(),
                            fmt
                        ).date()
                        break
                    except ValueError:
                        pass

                if order_date is None:
                    raise Exception(
                        f"Invalid order_date format: {order_date_value}"
                    )

                # ---------------------------------------------------
                # Required field: sales_amount
                # ---------------------------------------------------
                
                try:
                    sales_amount = Decimal(str(row.get("sales_amount", 0) or 0))
                except (InvalidOperation, ValueError):
                    sales_amount = Decimal("0")

                # ---------------------------------------------------
                # Base fields (only if they exist in model)
                # ---------------------------------------------------
                defaults = {}

                if "order_date" in order_model_fields:
                    defaults["order_date"] = order_date

                if "employee_id" in order_model_fields:
                    defaults["employee_id"] = str(
                        row.get("employee_id", "")
                    ).strip()

                if "position_name" in order_model_fields:
                    defaults["position_name"] = str(
                        row.get("position_name", "")
                    ).strip()

                if "sales_amount" in order_model_fields:
                    defaults["sales_amount"] = Decimal(str(sales_amount))

                if "order_status" in order_model_fields:
                    defaults["order_status"] = (
                        str(
                            row.get("order_status", "Booked")
                        ).strip() or "Booked"
                    )

                if "currency" in order_model_fields:
                    defaults["currency"] = (
                        str(
                            row.get("currency", "INR")
                        ).strip() or "INR"
                    )

                # ---------------------------------------------------
                # Optional text fields
                # Added only if both:
                # 1. CSV contains the column
                # 2. Model contains the field
                # ---------------------------------------------------
                optional_text_fields = [
                    "customer_name",
                    "product_name",
                    "service_name",
                ]

                for field_name in optional_text_fields:
                    if (
                        field_name in row
                        and field_name in order_model_fields
                    ):
                        defaults[field_name] = str(
                            row.get(field_name, "")
                        ).strip()

                # ---------------------------------------------------
                # Optional numeric field: quantity
                # Added only if model has quantity field
                # ---------------------------------------------------
                if (
                    "quantity" in row
                    and "quantity" in order_model_fields
                    and str(row.get("quantity", "")).strip()
                ):
                    defaults["quantity"] = float(
                        row.get("quantity")
                    )

                # ---------------------------------------------------
                # Create or update order
                # ---------------------------------------------------
                order, created = Order.objects.update_or_create(
                    order_id=order_id,
                    defaults=defaults
                )

            # 👉 AUTO COMMISSION CALCULATION HERE
                calculate_commission_for_order(order)

                success += 1

                

            except Exception as e:
                failed += 1
                errors.append({
                    "row": index,
                    "error": str(e),
                })
                print(
                    f"Error processing row {index}: {str(e)}"
                )

        # ---------------------------------------------------
        # Final response
        # ---------------------------------------------------
        return Response({
            "message": "Order upload completed successfully",
            "success": success,
            "failed": failed,
            "errors": errors[:20],
        })


# =====================================================
# Email-Based Login
# =====================================================
@api_view(['POST'])
@permission_classes([AllowAny])
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
            logger.warning(f"Login attempt with non-existent email: {email}")
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
    
    # Check password
    if not user.check_password(password):
        logger.warning(f"Failed login attempt for email: {email}")
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
        token, _ = Token.objects.get_or_create(user=user)
        
        # Get user profile for additional info
        user_profile = UserProfile.objects.filter(email=user.email).first()
        
        logger.info(f"Successful login for email: {email}")
        
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
        
        return Response({
            'user_id': user.id,
            'email': user.email,
            'role': user_profile.role,
            'name': user_profile.name,
            'is_admin': is_admin,
            'employee_id': user_profile.employee_id,
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