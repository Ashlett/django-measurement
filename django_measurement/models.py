import logging
import warnings

from django.db.models import FloatField
from django.utils.translation import gettext_lazy as _
from measurement import measures
from measurement.base import BidimensionalMeasure, MeasureBase

from . import forms
from .utils import get_measurement

logger = logging.getLogger("django_measurement")


class MeasurementField(FloatField):
    description = "Easily store, retrieve, and convert python measures."
    empty_strings_allowed = False
    MEASURE_BASES = (
        BidimensionalMeasure,
        MeasureBase,
    )
    default_error_messages = {
        "invalid_type": _(
            "'%(value)s' (%(type_given)s) value" " must be of type %(type_wanted)s."
        ),
    }

    def __init__(
        self,
        verbose_name=None,
        name=None,
        measurement=None,
        measurement_class=None,
        unit_choices=None,
        *args,
        **kwargs
    ):

        if not measurement and measurement_class is not None:
            warnings.warn(
                '"measurement_class" will be removed in version 4.0', DeprecationWarning
            )
            measurement = getattr(measures, measurement_class)

        if not measurement:
            raise TypeError(
                "MeasurementField() takes a measurement"
                " keyword argument. None given."
            )

        if not issubclass(measurement, self.MEASURE_BASES):
            raise TypeError(
                "MeasurementField() takes a measurement keyword argument."
                " It has to be a valid MeasureBase subclass."
            )

        self.measurement = measurement
        self.widget_args = {
            "measurement": measurement,
            "unit_choices": unit_choices,
        }

        super(MeasurementField, self).__init__(verbose_name, name, *args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(MeasurementField, self).deconstruct()
        kwargs["measurement"] = self.measurement
        return name, path, args, kwargs

    def get_prep_value(self, value):
        if value is None:
            return None

        elif isinstance(value, self.MEASURE_BASES):
            # sometimes we get sympy.core.numbers.Float, which the
            # database does not understand, so explicitely convert to
            # float

            return float(value.standard)

        else:
            return super(MeasurementField, self).get_prep_value(value)

    def get_default_unit(self):
        unit_choices = self.widget_args["unit_choices"]
        if unit_choices:
            return unit_choices[0][0]
        return self.measurement.STANDARD_UNIT

    def from_db_value(self, value, *args, **kwargs):
        if value is None:
            return None

        return get_measurement(
            measure=self.measurement,
            value=value,
            original_unit=self.get_default_unit(),
        )

    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        if not isinstance(value, self.MEASURE_BASES):
            return value
        return "%s:%s" % (value.value, value.unit)

    def deserialize_value_from_string(self, s: str):
        parts = s.split(":", 1)
        if len(parts) != 2:
            return None
        value, unit = float(parts[0]), parts[1]
        measure = get_measurement(self.measurement, value=value, unit=unit)
        return measure

    def to_python(self, value):

        if value is None:
            return value
        elif isinstance(value, self.MEASURE_BASES):
            return value
        elif isinstance(value, str):
            parsed = self.deserialize_value_from_string(value)
            if parsed is not None:
                return parsed
        value = super(MeasurementField, self).to_python(value)

        return_unit = self.get_default_unit()

        msg = (
            'You assigned a %s instead of %s to %s.%s.%s, unit was guessed to be "%s".'
            % (
                type(value).__name__,
                str(self.measurement.__name__),
                self.model.__module__,
                self.model.__name__,
                self.name,
                return_unit,
            )
        )
        logger.warning(msg)
        return get_measurement(
            measure=self.measurement,
            value=value,
            unit=return_unit,
        )

    def formfield(self, **kwargs):
        defaults = {"form_class": forms.MeasurementField}
        defaults.update(kwargs)
        defaults.update(self.widget_args)
        return super(MeasurementField, self).formfield(**defaults)
