# Pays par devise (pour segmentation des offres et agrégation des meilleurs taux)
# Liste (code_iso, nom). Vide ou une entrée "" = pas de filtre pays (global).

# Zone XOF (Afrique de l'Ouest - UEMOA)
XOF_COUNTRIES = [
    ("BJ", "Bénin"),
    ("BF", "Burkina Faso"),
    ("CI", "Côte d'Ivoire"),
    ("GW", "Guinée-Bissau"),
    ("ML", "Mali"),
    ("NE", "Niger"),
    ("SN", "Sénégal"),
    ("TG", "Togo"),
]

# Ghana
GHS_COUNTRIES = [("GH", "Ghana")]

# Nigeria
NGN_COUNTRIES = [("NG", "Nigeria")]

# Zone XAF (Afrique centrale - CEMAC)
XAF_COUNTRIES = [
    ("CM", "Cameroun"),
    ("CF", "République centrafricaine"),
    ("TD", "Tchad"),
    ("CG", "Congo"),
    ("GQ", "Guinée équatoriale"),
    ("GA", "Gabon"),
]

# Autres Afrique de l'Ouest
GMD_COUNTRIES = [("GM", "Gambie")]
SLL_COUNTRIES = [("SL", "Sierra Leone")]
LRD_COUNTRIES = [("LR", "Liberia")]
GNF_COUNTRIES = [("GN", "Guinée")]
MRU_COUNTRIES = [("MR", "Mauritanie")]

# Afrique (autres régions, souvent présentes sur P2P)
KES_COUNTRIES = [("KE", "Kenya")]
TZS_COUNTRIES = [("TZ", "Tanzanie")]
RWF_COUNTRIES = [("RW", "Rwanda")]
UGX_COUNTRIES = [("UG", "Ouganda")]
ZAR_COUNTRIES = [("ZA", "Afrique du Sud")]
ETB_COUNTRIES = [("ET", "Éthiopie")]

# Grandes devises (pas de segmentation pays : une seule option "global")
MAJOR_FIAT = ["USD", "EUR", "GBP", "CHF", "CAD", "AUD", "CNY", "JPY", "TRY", "INR", "BRL", "MXN"]

# Toutes devises supportées : Afrique de l'Ouest + Afrique + grandes devises
SUPPORTED_FIAT = [
    # Afrique de l'Ouest
    "XOF",
    "GHS",
    "NGN",
    "XAF",
    "GMD",
    "SLL",
    "LRD",
    "GNF",
    "MRU",
    # Autres Afrique
    "KES",
    "TZS",
    "RWF",
    "UGX",
    "ZAR",
    "ETB",
    # Grandes devises
    "USD",
    "EUR",
    "GBP",
    "CHF",
    "CAD",
    "AUD",
    "CNY",
    "JPY",
    "TRY",
    "INR",
    "BRL",
    "MXN",
]

# Mapping devise -> liste (code_pays, nom) pour l'agrégation. Vide = [("", "Global")].
FIAT_COUNTRIES = {
    "XOF": XOF_COUNTRIES,
    "GHS": GHS_COUNTRIES,
    "NGN": NGN_COUNTRIES,
    "XAF": XAF_COUNTRIES,
    "GMD": GMD_COUNTRIES,
    "SLL": SLL_COUNTRIES,
    "LRD": LRD_COUNTRIES,
    "GNF": GNF_COUNTRIES,
    "MRU": MRU_COUNTRIES,
    "KES": KES_COUNTRIES,
    "TZS": TZS_COUNTRIES,
    "RWF": RWF_COUNTRIES,
    "UGX": UGX_COUNTRIES,
    "ZAR": ZAR_COUNTRIES,
    "ETB": ETB_COUNTRIES,
}
# Grandes devises : pas de pays, une seule clé ""
for _f in MAJOR_FIAT:
    if _f not in FIAT_COUNTRIES:
        FIAT_COUNTRIES[_f] = [("", "Global")]
