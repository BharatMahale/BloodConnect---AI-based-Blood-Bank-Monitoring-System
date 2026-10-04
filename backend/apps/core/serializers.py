from rest_framework import serializers


class HealthCheckSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("healthy", "unhealthy"))
    service = serializers.CharField()
    database = serializers.ChoiceField(choices=("connected", "disconnected"))


class CountPairSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    completed = serializers.IntegerField(required=False)
    available = serializers.IntegerField(required=False)
    verified = serializers.IntegerField(required=False)


class RequestSummarySerializer(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    completed = serializers.IntegerField()
    by_status = serializers.DictField(child=serializers.IntegerField())


class InventorySummarySerializer(serializers.Serializer):
    total_units = serializers.IntegerField()
    reserved_units = serializers.IntegerField()
    available_units = serializers.IntegerField()


class InventoryBloodGroupSummarySerializer(InventorySummarySerializer):
    blood_group = serializers.CharField()


class PublicInventorySummarySerializer(serializers.Serializer):
    total_units = serializers.IntegerField()
    available_units = serializers.IntegerField()


class PublicInventoryBloodGroupSummarySerializer(
    PublicInventorySummarySerializer
):
    blood_group = serializers.CharField()


class PublicInventorySerializer(serializers.Serializer):
    summary = PublicInventorySummarySerializer()
    by_blood_group = PublicInventoryBloodGroupSummarySerializer(
        many=True
    )


class PublicDashboardSerializer(serializers.Serializer):
    blood_banks = CountPairSerializer()
    donors = CountPairSerializer()
    requests = RequestSummarySerializer()
    donations = CountPairSerializer()
    inventory = PublicInventorySerializer()


class DashboardAccountSerializer(serializers.Serializer):
    email = serializers.EmailField()


class DashboardNotificationSerializer(serializers.Serializer):
    unread = serializers.IntegerField()


class DashboardDonorSerializer(serializers.Serializer):
    has_profile = serializers.BooleanField()
    is_available = serializers.BooleanField()
    is_eligible = serializers.BooleanField(allow_null=True)
    blood_group = serializers.CharField(allow_null=True)
    donation_count = serializers.IntegerField()
    last_donation_date = serializers.DateField(allow_null=True)


class BloodBankManagementSerializer(serializers.Serializer):
    owned_banks = serializers.IntegerField()
    assigned_requests = serializers.IntegerField()
    active_assigned_requests = serializers.IntegerField()
    inventory = InventorySummarySerializer()
    inventory_by_blood_group = InventoryBloodGroupSummarySerializer(many=True)


class MyDashboardSerializer(serializers.Serializer):
    account = DashboardAccountSerializer()
    notifications = DashboardNotificationSerializer()
    my_requests = RequestSummarySerializer()
    donor = DashboardDonorSerializer()
    blood_bank_management = BloodBankManagementSerializer()
