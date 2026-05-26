from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import upload_orders
from .views import (
    EmployeeViewSet,
    SaleViewSet,
    CommissionViewSet,
    SCRateTableViewSet,
    SCFlatRateTableViewSet,
    UserProfileListCreateView,
    UserProfileUploadView,
    CompensationPlanListCreateView,
    CompensationTierListCreateView,
    OrderListCreateView
)
from . import views

from .views import signup, login, email_login, change_password, get_user_profile
from .views import HierarchyRelationshipListCreateView

router = DefaultRouter()
router.register('employees', EmployeeViewSet)
router.register('sales', SaleViewSet)
router.register('commissions', CommissionViewSet, basename='commission')
router.register('sc-rate-tables', SCRateTableViewSet, basename='sc-rate-table')
router.register('sc-flat-rate-tables', SCFlatRateTableViewSet, basename='sc-flat-rate-table')

urlpatterns = [
    path('', include(router.urls)),
    path('upload-orders/', upload_orders),
    path('signup/', signup),
    path('login/', login),
    path('email-login/', email_login, name='email-login'),
    path('change-password/', change_password, name='change-password'),
    path('user-profile/', get_user_profile, name='user-profile'),
    path(
    'compensation-plans/',
    CompensationPlanListCreateView.as_view(),
    name='compensation-plans'
),
path(
    'user-setup/',
    UserProfileListCreateView.as_view(),
    name='user-setup'
),
path(
    'user-setup-upload/',
    UserProfileUploadView.as_view(),
    name='user-setup-upload'
),
path(
    'hierarchy-relationships/',
    HierarchyRelationshipListCreateView.as_view(),
    name='hierarchy-relationships'
),
path(
    'compensation-plans/',
    CompensationPlanListCreateView.as_view()
),

path(
    'compensation-tiers/',
    CompensationTierListCreateView.as_view()
),
path(
    "orders/",
    OrderListCreateView.as_view(),
    name="orders"
),
path('orders-upload/', views.OrderUploadView.as_view(), name='orders-upload'),


]
