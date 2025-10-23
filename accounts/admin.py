# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
# Import the new models
from .models import CustomUser, Friendship, FriendTransaction

# --- Keep the existing CustomUserAdmin class here ---
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('username', 'first_name', 'last_name', 'is_staff', 'is_active')
    search_fields = ('username', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_active', 'is_superuser')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password', 'password2'),
        }),
    )
    ordering = ('username',)

admin.site.register(CustomUser, CustomUserAdmin)
# --- End of existing CustomUserAdmin ---


# --- Register Friendship Model ---
@admin.register(Friendship) # Alternative way to register using a decorator
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ('requester', 'receiver', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('requester__username', 'receiver__username')
    ordering = ('-created_at',)
    # Make fields read-only in the admin after creation if desired
    readonly_fields = ('requester', 'receiver', 'created_at', 'updated_at')


# --- Register FriendTransaction Model ---
@admin.register(FriendTransaction)
class FriendTransactionAdmin(admin.ModelAdmin):
    list_display = ('initiator', 'friend', 'amount', 'status', 'created_at', 'updated_at', 'action_taken_by')
    list_filter = ('status', 'created_at', 'initiator', 'friend')
    search_fields = ('initiator__username', 'friend__username', 'description')
    ordering = ('-created_at',)
    # You might want to make some fields read-only depending on the status
    readonly_fields = ('created_at', 'updated_at', 'action_taken_by')

    # Example: Make fields read-only once accepted/rejected
    # def get_readonly_fields(self, request, obj=None):
    #     if obj and obj.status != FriendTransaction.StatusChoices.PENDING:
    #         # Make these fields read-only if the transaction is not pending anymore
    #         return self.readonly_fields + ('initiator', 'friend', 'amount', 'description', 'status')
    #     return self.readonly_fields