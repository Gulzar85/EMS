import copy

import factory
from factory.django import DjangoModelFactory

from apps.theme.models import Theme, ThemeVersion
from apps.theme.validation import DEFAULT_THEME_TOKENS


class ThemeFactory(DjangoModelFactory):
    class Meta:
        model = Theme

    name = factory.Sequence(lambda n: f"Theme {n}")
    description = "A test theme"


class ThemeVersionFactory(DjangoModelFactory):
    class Meta:
        model = ThemeVersion

    theme = factory.SubFactory(ThemeFactory)
    version_number = 1
    status = ThemeVersion.Status.DRAFT
    tokens = factory.LazyFunction(lambda: copy.deepcopy(DEFAULT_THEME_TOKENS))
