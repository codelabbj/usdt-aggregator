# Data migration: préremplit les devises et pays d'Afrique de l'Ouest.
# Le reste (XAF, KES, USD, etc.) pourra être ajouté plus tard dans l'admin.

from django.db import migrations


def seed_west_africa(apps, schema_editor):
    Currency = apps.get_model("core", "Currency")
    Country = apps.get_model("core", "Country")

    # Afrique de l'Ouest : devise -> [(code_pays, nom_pays), ...]
    data = [
        ("XOF", "Franc CFA BCEAO (UEMOA)", [
            ("BJ", "Bénin"),
            ("BF", "Burkina Faso"),
            ("CI", "Côte d'Ivoire"),
            ("GW", "Guinée-Bissau"),
            ("ML", "Mali"),
            ("NE", "Niger"),
            ("SN", "Sénégal"),
            ("TG", "Togo"),
        ]),
        ("GHS", "Cedi ghanéen", [("GH", "Ghana")]),
        ("NGN", "Naira nigérian", [("NG", "Nigeria")]),
        ("GMD", "Dalasi gambien", [("GM", "Gambie")]),
        ("SLL", "Leone sierra-léonais", [("SL", "Sierra Leone")]),
        ("LRD", "Dollar libérien", [("LR", "Liberia")]),
        ("GNF", "Franc guinéen", [("GN", "Guinée")]),
        ("MRU", "Ouguiya mauritanien", [("MR", "Mauritanie")]),
    ]

    for order, (code, name, countries) in enumerate(data, start=1):
        currency, _ = Currency.objects.get_or_create(
            code=code,
            defaults={"name": name, "active": True, "order": order},
        )
        for i, (country_code, country_name) in enumerate(countries, start=1):
            Country.objects.get_or_create(
                currency=currency,
                code=country_code,
                defaults={"name": country_name, "active": True, "order": i},
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_add_currency_and_country"),
    ]

    operations = [
        migrations.RunPython(seed_west_africa, noop),
    ]
