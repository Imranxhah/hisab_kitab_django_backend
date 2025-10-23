# Step 5: Enhanced admin.py with custom styling hooks
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from .models import CustomUser, Friendship, FriendTransaction


# Custom User Creation Form
class CustomUserCreationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': 'vTextField',
            'placeholder': 'Enter password'
        }),
        strip=False,
    )
    password2 = forms.CharField(
        label='Password confirmation',
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': 'vTextField',
            'placeholder': 'Confirm password'
        }),
        strip=False,
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'first_name', 'last_name')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'vTextField', 'placeholder': 'Username'}),
            'first_name': forms.TextInput(attrs={'class': 'vTextField', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'vTextField', 'placeholder': 'Last name'}),
        }

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class CustomUserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        label="Password",
        help_text=(
            "Raw passwords are not stored. "
            "<a href=\"../password/\">Change password</a>."
        ),
    )

    class Meta:
        model = CustomUser
        fields = '__all__'


class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = ('username_badge', 'full_name', 'user_status', 'staff_badge', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'is_superuser', 'date_joined')
    
    fieldsets = (
        ('Account Info', {'fields': ('username', 'password')}),
        ('Personal Details', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        ('Create New User', {
            'classes': ('wide',),
            'fields': ('username', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )
    
    search_fields = ('username', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    filter_horizontal = ('groups', 'user_permissions',)

    def username_badge(self, obj):
        return format_html(
            '<span class="username-badge">{}</span>',
            obj.username
        )
    username_badge.short_description = 'Username'

    def full_name(self, obj):
        name = obj.get_full_name()
        return name if name else '—'
    full_name.short_description = 'Full Name'

    def user_status(self, obj):
        if obj.is_active:
            return format_html('<span class="status-badge status-active">Active</span>')
        return format_html('<span class="status-badge status-inactive">Inactive</span>')
    user_status.short_description = 'Status'

    def staff_badge(self, obj):
        if obj.is_superuser:
            return format_html('<span class="role-badge role-superuser">Superuser</span>')
        elif obj.is_staff:
            return format_html('<span class="role-badge role-staff">Staff</span>')
        return format_html('<span class="role-badge role-user">User</span>')
    staff_badge.short_description = 'Role'


admin.site.register(CustomUser, CustomUserAdmin)


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ('requester_display', 'receiver_display', 'status_badge', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('requester__username', 'receiver__username')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Friend Request', {
            'fields': ('requester', 'receiver', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def requester_display(self, obj):
        return format_html('<strong>{}</strong>', obj.requester.username)
    requester_display.short_description = 'Requester'

    def receiver_display(self, obj):
        return format_html('<strong>{}</strong>', obj.receiver.username)
    receiver_display.short_description = 'Receiver'

    def status_badge(self, obj):
        colors = {
            'pending': 'status-pending',
            'accepted': 'status-accepted',
            'rejected': 'status-rejected'
        }
        return format_html(
            '<span class="status-badge {}">{}</span>',
            colors.get(obj.status, ''),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(FriendTransaction)
class FriendTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_summary', 'amount_display', 'status_badge', 'created_at', 'action_taken_by')
    list_filter = ('status', 'created_at', 'initiator', 'friend')
    search_fields = ('initiator__username', 'friend__username', 'description')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('initiator', 'friend', 'amount', 'description')
        }),
        ('Status', {
            'fields': ('status', 'action_taken_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def transaction_summary(self, obj):
        return format_html(
            '<strong>{}</strong> ➜ <strong>{}</strong>',
            obj.initiator.username,
            obj.friend.username
        )
    transaction_summary.short_description = 'Transaction'

    def amount_display(self, obj):
        color = 'amount-positive' if obj.amount > 0 else 'amount-negative'
        return format_html(
            '<span class="{}">${}</span>',
            color,
            abs(obj.amount)
        )
    amount_display.short_description = 'Amount'

    def status_badge(self, obj):
        colors = {
            'pending': 'status-pending',
            'accepted': 'status-accepted',
            'rejected': 'status-rejected'
        }
        return format_html(
            '<span class="status-badge {}">{}</span>',
            colors.get(obj.status, ''),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status != FriendTransaction.StatusChoices.PENDING:
            return self.readonly_fields + ('initiator', 'friend', 'amount', 'description', 'status', 'action_taken_by')
        return self.readonly_fields


# Customize admin site header and title
admin.site.site_header = "Hisab Kitab Administration"
admin.site.site_title = "Hisab Kitab Admin"
admin.site.index_title = "Welcome to Hisab Kitab Admin Portal"