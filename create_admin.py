#!/usr/bin/env python
"""
Script to create an admin user for the Sales Compensation Platform
Run this from the backend directory: python create_admin.py
"""

import os
import django
from django.contrib.auth.models import User

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from commissions.models import UserProfile
from commissions.tenants import get_default_organization

def create_admin_user():
    """Create admin user if it doesn't exist"""
    
    admin_email = 'admin@company.com'
    admin_password = 'Welcome@123'
    
    print("=" * 60)
    print("🔐 Sales Compensation Platform - Admin User Setup")
    print("=" * 60)
    print()
    
    # Check if user already exists
    existing_user = User.objects.filter(email=admin_email).first()
    if existing_user:
        print(f"⚠️  User {admin_email} already exists!")
        print(f"   Username: {existing_user.username}")
        print(f"   Active: {existing_user.is_active}")
        
        # Check if profile exists
        profile = UserProfile.objects.filter(email=admin_email).first()
        if profile:
            print(f"   Profile Role: {profile.role}")
        print()
        return
    
    # Create Django user
    print(f"📝 Creating Django user...")
    django_user = User.objects.create_user(
        username=admin_email,
        email=admin_email,
        password=admin_password,
        first_name='Admin',
        last_name='User',
        is_active=True
    )
    print(f"   ✅ User created: {django_user.email}")
    print()
    
    # Create UserProfile
    print(f"📝 Creating UserProfile...")
    profile = UserProfile.objects.create(
        organization=get_default_organization(),
        email=admin_email,
        name='Admin User',
        first_name='Admin',
        last_name='User',
        role='admin',
        employee_id='ADMIN001',
        position_name='Administrator',
        title='System Administrator',
        enable_login=True,
        business_group='Company HQ'
    )
    print(f"   ✅ Profile created with role: {profile.role}")
    print()
    
    # Display credentials
    print("=" * 60)
    print("✅ ADMIN USER CREATED SUCCESSFULLY!")
    print("=" * 60)
    print()
    print("📋 Login Credentials:")
    print(f"   Email: {admin_email}")
    print(f"   Password: {admin_password}")
    print()
    print("🌐 You can now login at: http://localhost:3000/login")
    print()
    print("🔐 IMPORTANT:")
    print("   1. Use these credentials to login")
    print("   2. After first login, go to Change Password")
    print("   3. Set a strong password (not Welcome@123)")
    print()
    print("✨ After login, you will see:")
    print("   - Sidebar badge: 👑 Admin")
    print("   - All 6 menu items:")
    print("     • Dashboard")
    print("     • User Setup")
    print("     • Employees")
    print("     • Commissions")
    print("     • Comp Plans")
    print("     • Orders")
    print()

if __name__ == '__main__':
    try:
        create_admin_user()
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
