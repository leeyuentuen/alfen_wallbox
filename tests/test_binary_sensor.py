"""Test the Alfen Wallbox binary sensor entities."""


from homeassistant.const import EntityCategory

from custom_components.alfen_wallbox.binary_sensor import ALFEN_BINARY_SENSOR_TYPES


class TestBinarySensorEntityCategories:
    """Tests for binary sensor entity categories."""

    def test_license_sensors_have_diagnostic_category(self):
        """Test that all license sensors have DIAGNOSTIC entity category."""
        license_sensors = [
            desc for desc in ALFEN_BINARY_SENSOR_TYPES
            if desc.key.startswith("license_")
        ]

        assert len(license_sensors) > 0, "Should have license sensors"

        for desc in license_sensors:
            assert desc.entity_category == EntityCategory.DIAGNOSTIC, (
                f"License sensor {desc.key} should have DIAGNOSTIC category"
            )

    def test_system_sensors_have_diagnostic_category(self):
        """Test that system sensors have DIAGNOSTIC entity category."""
        system_sensors = [
            desc for desc in ALFEN_BINARY_SENSOR_TYPES
            if desc.key in ["system_date_light_savings", "https_api_login_status"]
        ]

        for desc in system_sensors:
            assert desc.entity_category == EntityCategory.DIAGNOSTIC, (
                f"System sensor {desc.key} should have DIAGNOSTIC category"
            )

    def test_all_binary_sensors_have_entity_category(self):
        """Test that all binary sensors have an entity category defined."""
        for desc in ALFEN_BINARY_SENSOR_TYPES:
            assert desc.entity_category is not None, (
                f"Binary sensor {desc.key} should have entity_category defined"
            )


class TestBinarySensorDescriptions:
    """Tests for binary sensor descriptions."""

    def test_all_sensors_have_key(self):
        """Test that all binary sensors have a key."""
        for desc in ALFEN_BINARY_SENSOR_TYPES:
            assert desc.key is not None
            assert len(desc.key) > 0

    def test_all_sensors_have_name(self):
        """Test that all binary sensors have a name."""
        for desc in ALFEN_BINARY_SENSOR_TYPES:
            assert desc.name is not None
            assert len(desc.name) > 0

    def test_license_sensor_count(self):
        """Test expected number of license sensors."""
        license_sensors = [
            desc for desc in ALFEN_BINARY_SENSOR_TYPES
            if desc.key.startswith("license_")
        ]
        # Should have: scn, active_loadbalancing, static_loadbalancing,
        # high_power_sockets, rfid_reader, personalized_display, mobile_3G_4G, giro_e
        assert len(license_sensors) == 8

    def test_https_api_login_status_has_connectivity_device_class(self):
        """Test that API login status has connectivity device class."""
        from homeassistant.components.binary_sensor import BinarySensorDeviceClass

        api_sensor = next(
            (desc for desc in ALFEN_BINARY_SENSOR_TYPES
             if desc.key == "https_api_login_status"),
            None
        )

        assert api_sensor is not None
        assert api_sensor.device_class == BinarySensorDeviceClass.CONNECTIVITY
