import streamlit as st
import pandas as pd
from pathlib import Path
import plotly.express as px

st.set_page_config(
    page_title="DataTourisme Quadria",
    page_icon="https://quadria-ppr.inr.ag/content/uploads/2026/05/QUADRIA_LOGO_FLECHE_BLANC.png",
    layout="wide"
)

COMMERCIAL_MAP_CANDIDATES = [
    "affectation_commerciaux.csv",
    "affectation_commerciaux.xlsx",
    "secteurs_commerciaux.csv",
    "secteurs_commerciaux.xlsx",
]


COORDS_CANDIDATES = [
    "communes_coords.csv",
    "communes_coords.xlsx",
    "communes_france.csv",
    "communes_france.xlsx",
]


@st.cache_data
def load_main_data():
    base_dir = Path(__file__).parent
    candidates = list(base_dir.glob("*.csv"))
    if not candidates:
        raise FileNotFoundError(f"Aucun .csv trouvé dans {base_dir}")

    picked = None
    for p in candidates:
        n = p.name.lower()
        if "bergement" in n or "hebergement" in n:
            picked = p
            break
    if picked is None:
        picked = candidates[0]

    df = pd.read_csv(picked, sep=";", dtype=str, encoding="utf-8").fillna("")
    return df, str(picked.name)


@st.cache_data
def load_commercial_mapping():
    base_dir = Path(__file__).parent
    path = None
    for name in COMMERCIAL_MAP_CANDIDATES:
        p = base_dir / name
        if p.exists():
            path = p
            break
    if path is None:
        return None, "Aucun fichier affectation commerciaux trouvé (affectation_commerciaux.csv/.xlsx)"

    try:
        if path.suffix.lower() in [".xlsx", ".xls"]:
            # nécessite openpyxl si xlsx
            df_map = pd.read_excel(path, dtype=str).fillna("")
        else:
            df_map = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8").fillna("")
    except Exception as e:
        return None, f"Impossible de lire {path.name}: {e}"

    cols = {c.strip().upper(): c for c in df_map.columns}
    if "COMMERCIAL" not in cols or "DEPT" not in cols:
        return None, f"Colonnes attendues dans {path.name}: Commercial, DEPT (trouvées: {list(df_map.columns)})"

    df_map["COMMERCIAL"] = df_map[cols["COMMERCIAL"]].astype(str).str.strip()
    df_map["DEPT"] = df_map[cols["DEPT"]].astype(str).str.strip()

    # dept sur 2 chiffres quand numérique
    df_map["DEPT"] = df_map["DEPT"].apply(lambda x: x.zfill(2) if x.isdigit() else x)

    df_map = df_map[(df_map["COMMERCIAL"] != "") & (df_map["DEPT"] != "")]
    return df_map[["COMMERCIAL", "DEPT"]], f"{path.name} ({len(df_map)} lignes)"


@st.cache_data
def load_coords():
    base_dir = Path(__file__).parent
    path = None
    for name in COORDS_CANDIDATES:
        p = base_dir / name
        if p.exists():
            path = p
            break
    if path is None:
        return None, "Aucun fichier coords communes trouvé (communes_coords.csv/.xlsx)"

    try:
        if path.suffix.lower() in [".xlsx", ".xls"]:
            dfc = pd.read_excel(path, dtype=str).fillna("")
        else:
            dfc = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8").fillna("")
    except Exception as e:
        return None, f"Impossible de lire {path.name}: {e}"

    cols = {c.strip().upper(): c for c in dfc.columns}
    needed = ["COMMUNE", "DEPT", "CODE POSTAL", "LAT", "LON"]
    missing = [k for k in needed if k not in cols]
    if missing:
        return None, f"{path.name} colonnes manquantes: {missing}. Trouvées: {list(dfc.columns)}"

    out = pd.DataFrame({
        "COMMUNE": dfc[cols["COMMUNE"]].astype(str).str.strip(),
        "DEPT": dfc[cols["DEPT"]].astype(str).str.strip(),
        "CODE POSTAL": dfc[cols["CODE POSTAL"]].astype(str).str.strip(),
        "LAT": pd.to_numeric(dfc[cols["LAT"]], errors="coerce"),
        "LON": pd.to_numeric(dfc[cols["LON"]], errors="coerce"),
    }).dropna(subset=["LAT", "LON"])

    out["DEPT"] = out["DEPT"].apply(lambda x: x.zfill(2) if x.isdigit() else x)
    out["CP_KEY"] = out["CODE POSTAL"].str.replace(" ", "", regex=False)
    out["COMMUNE_KEY"] = out["COMMUNE"].str.lower().str.replace(r"\s+", " ", regex=True).str.strip()

    return out[["COMMUNE", "DEPT", "CODE POSTAL", "CP_KEY", "COMMUNE_KEY", "LAT", "LON"]], f"{path.name} ({len(out)} lignes)"


def to_int_series(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip()
    s = s.str.replace("\u202f", "", regex=False)
    s = s.str.replace("\xa0", "", regex=False)
    s = s.str.replace(" ", "", regex=False)
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


# Échelle demandée
def cap_bucket(x):
    if pd.isna(x):
        return "Inconnue"
    x = float(x)
    if x <= 50:
        return "≤ 50"
    if 50 < x <= 200:
        return "51–200"
    if 200 < x <= 400:
        return "201–400"
    if 400 < x <= 800:
        return "401–800"
    return "≥ 801"


def reset_filters():
    keys = [
        "commercial",
        "override_dept",
        "q",
        "selected_depts",
        "cp_search",
        "selected_tranche",
        "selected_commune",
        "selected_typo",
        "selected_classement",
    ]
    for k in keys:
        st.session_state.pop(k, None)



try:
    df, main_info = load_main_data()
except Exception as e:
    st.error("Erreur au chargement du CSV hébergements.")
    st.exception(e)
    st.stop()

df_map, map_info = load_commercial_mapping()
df_coords, coords_info = load_coords()

st.title("🏨 Base prospects – Hébergements touristiques")
st.caption(f"CSV chargé : {main_info} · {len(df):,} lignes")


df["CODE POSTAL"] = df.get("CODE POSTAL", "").astype(str).str.strip()
df["DEPT"] = df["CODE POSTAL"].str[:2]
df["DEPT"] = df["DEPT"].apply(lambda x: x.zfill(2) if x.isdigit() else x)

df["COMMUNE"] = df.get("COMMUNE", "").astype(str).str.strip()
df["CP_KEY"] = df["CODE POSTAL"].str.replace(" ", "", regex=False)
df["COMMUNE_KEY"] = df["COMMUNE"].str.lower().str.replace(r"\s+", " ", regex=True).str.strip()

cap_col = "CAPACITÉ D'ACCUEIL (PERSONNES)"
if cap_col in df.columns:
    df["CAP_NUM"] = to_int_series(df[cap_col])
    df["TRANCHE_CAPACITE"] = df["CAP_NUM"].apply(cap_bucket)
else:
    df["CAP_NUM"] = pd.NA
    df["TRANCHE_CAPACITE"] = "Inconnue"

commune_col = "COMMUNE"
typologie_col = "TYPOLOGIE ÉTABLISSEMENT"
classement_col = "CLASSEMENT"


st.sidebar.header("Filtres")

if st.sidebar.button("🔄 Réinitialiser tous les filtres"):
    reset_filters()
    st.rerun()


commercials = []
if df_map is not None and "COMMERCIAL" in df_map.columns:
    df_map["COMMERCIAL"] = (
        df_map["COMMERCIAL"].astype(str)
        .str.replace("\u202f", " ", regex=False)  # espace fine
        .str.replace("\xa0", " ", regex=False)    # espace insécable
        .str.strip()
    )
    commercials = sorted([c for c in df_map["COMMERCIAL"].dropna().unique().tolist() if c])

if "commercial" not in st.session_state:
    st.session_state["commercial"] = "Tous"

# si la valeur en session_state n'est plus valide, on reset proprement
valid_commercials = ["Tous"] + commercials
if st.session_state["commercial"] not in valid_commercials:
    st.session_state["commercial"] = "Tous"

commercial = st.sidebar.selectbox("Commercial", valid_commercials, index=valid_commercials.index(st.session_state["commercial"]))
st.session_state["commercial"] = commercial

# Autoriser override dept
if "override_dept" not in st.session_state:
    st.session_state["override_dept"] = False

override_dept = st.sidebar.checkbox(
    "Autoriser modification manuelle des départements",
    value=st.session_state["override_dept"],
    disabled=(commercial == "Tous" or df_map is None),
)
st.session_state["override_dept"] = override_dept

# acine
q = st.sidebar.text_input("Recherche (nom/adresse/commune)", value=st.session_state.get("q", "")).strip()
st.session_state["q"] = q

cp_search = st.sidebar.text_input("Code postal (exact ou préfixe)", value=st.session_state.get("cp_search", "")).strip()
st.session_state["cp_search"] = cp_search

all_depts = sorted([d for d in df["DEPT"].dropna().unique().tolist() if d and d.lower() != "na"])

dept_from_commercial = None
if commercial != "Tous" and df_map is not None and "DEPT" in df_map.columns:
    # normalise aussi les DEPT côté mapping
    df_map["DEPT"] = (
        df_map["DEPT"].astype(str)
        .str.replace("\u202f", "", regex=False)
        .str.replace("\xa0", "", regex=False)
        .str.strip()
    )
    df_map["DEPT"] = df_map["DEPT"].apply(lambda x: x.zfill(2) if x.isdigit() else x)

    dept_from_commercial = sorted(df_map[df_map["COMMERCIAL"] == commercial]["DEPT"].unique().tolist())

# selected_depts (manuel ou forcé)
if "selected_depts" not in st.session_state:
    st.session_state["selected_depts"] = []

# si commercial choisi et pas override -> force en session_state
if dept_from_commercial is not None and not override_dept:
    st.session_state["selected_depts"] = dept_from_commercial

selected_depts = st.sidebar.multiselect(
    "Départements",
    options=all_depts,
    default=st.session_state.get("selected_depts", []),
    disabled=(dept_from_commercial is not None and not override_dept),
)
st.session_state["selected_depts"] = selected_depts

# >>> IMPORTANT : on définit UNE SEULE SOURCE DE VÉRITÉ pour les départements appliqués
if dept_from_commercial is not None and not override_dept:
    effective_depts = dept_from_commercial
else:
    effective_depts = selected_depts

# ---------------------------------------------------------
# Scope 1 (q + dept + cp) => utilisé pour rendre les listes dynamiques
# ---------------------------------------------------------
df_scope = df.copy()

if q:
    cols_to_search = [c for c in ["NOM COMMERCIAL", "ADRESSE", "COMMUNE"] if c in df_scope.columns]
    if cols_to_search:
        hay = df_scope[cols_to_search].astype(str).agg(" ".join, axis=1).str.lower()
        df_scope = df_scope[hay.str.contains(q.lower(), na=False)]

if effective_depts:
    df_scope = df_scope[df_scope["DEPT"].isin(effective_depts)]

if cp_search:
    df_scope = df_scope[df_scope["CODE POSTAL"].str.startswith(cp_search)]

# ---------------------------------------------------------
# Tranche capacité (dynamique)
# ---------------------------------------------------------
preferred = ["≤ 50", "51–200", "201–400", "401–800", "≥ 801", "Inconnue"]
vals = [t for t in df_scope["TRANCHE_CAPACITE"].dropna().unique().tolist() if t]
vals = [t for t in preferred if t in vals] + [t for t in vals if t not in preferred]
tranche_options = ["Toutes"] + vals

if "selected_tranche" not in st.session_state:
    st.session_state["selected_tranche"] = "Toutes"
if st.session_state["selected_tranche"] not in tranche_options:
    st.session_state["selected_tranche"] = "Toutes"

selected_tranche = st.sidebar.selectbox("Capacité (personnes)", tranche_options, index=tranche_options.index(st.session_state["selected_tranche"]))
st.session_state["selected_tranche"] = selected_tranche

df_scope2 = df_scope.copy()
if selected_tranche != "Toutes":
    df_scope2 = df_scope2[df_scope2["TRANCHE_CAPACITE"] == selected_tranche]

# ---------------------------------------------------------
# Commune (dynamique)
# ---------------------------------------------------------
communes = sorted([c for c in df_scope2[commune_col].dropna().unique().tolist() if c]) if commune_col in df_scope2.columns else []
commune_options = ["Toutes"] + communes

if "selected_commune" not in st.session_state:
    st.session_state["selected_commune"] = "Toutes"
if st.session_state["selected_commune"] not in commune_options:
    st.session_state["selected_commune"] = "Toutes"

selected_commune = st.sidebar.selectbox("Commune", commune_options, index=commune_options.index(st.session_state["selected_commune"]))
st.session_state["selected_commune"] = selected_commune

df_scope3 = df_scope2.copy()
if selected_commune != "Toutes":
    df_scope3 = df_scope3[df_scope3[commune_col] == selected_commune]

# ---------------------------------------------------------
# Typologie (dynamique)
# ---------------------------------------------------------
typos = sorted([t for t in df_scope3[typologie_col].dropna().unique().tolist() if t]) if typologie_col in df_scope3.columns else []
typo_options = ["Toutes"] + typos

if "selected_typo" not in st.session_state:
    st.session_state["selected_typo"] = "Toutes"
if st.session_state["selected_typo"] not in typo_options:
    st.session_state["selected_typo"] = "Toutes"

selected_typo = st.sidebar.selectbox("Typologie", typo_options, index=typo_options.index(st.session_state["selected_typo"]))
st.session_state["selected_typo"] = selected_typo

df_scope4 = df_scope3.copy()
if selected_typo != "Toutes":
    df_scope4 = df_scope4[df_scope4[typologie_col] == selected_typo]

# ---------------------------------------------------------
# Classement (dynamique)
# ---------------------------------------------------------
cls = sorted([c for c in df_scope4[classement_col].dropna().unique().tolist() if c]) if classement_col in df_scope4.columns else []
cl_options = ["Tous"] + cls

if "selected_classement" not in st.session_state:
    st.session_state["selected_classement"] = "Tous"
if st.session_state["selected_classement"] not in cl_options:
    st.session_state["selected_classement"] = "Tous"

selected_classement = st.sidebar.selectbox("Classement", cl_options, index=cl_options.index(st.session_state["selected_classement"]))
st.session_state["selected_classement"] = selected_classement

# Debug discret en bas des filtres
st.sidebar.markdown("""
<style>
[data-testid="stSidebar"] details {
    font-size: 0.78rem;
}
[data-testid="stSidebar"] details p,
[data-testid="stSidebar"] details div {
    font-size: 0.76rem;
}
</style>
""", unsafe_allow_html=True)

with st.sidebar.expander("Debug chargement fichiers", expanded=False):
    st.caption(f"Affectation commerciaux : {map_info}")
    st.caption(f"Coordonnées communes : {coords_info}")

# =========================================================
# APPLY FILTERS
# =========================================================
filtered = df.copy()

if q:
    cols_to_search = [c for c in ["NOM COMMERCIAL", "ADRESSE", "COMMUNE"] if c in filtered.columns]
    if cols_to_search:
        hay = filtered[cols_to_search].astype(str).agg(" ".join, axis=1).str.lower()
        filtered = filtered[hay.str.contains(q.lower(), na=False)]

if effective_depts:
    filtered = filtered[filtered["DEPT"].isin(effective_depts)]

if cp_search:
    filtered = filtered[filtered["CODE POSTAL"].str.startswith(cp_search)]

if selected_tranche != "Toutes":
    filtered = filtered[filtered["TRANCHE_CAPACITE"] == selected_tranche]

if selected_commune != "Toutes":
    filtered = filtered[filtered[commune_col] == selected_commune]

if selected_typo != "Toutes":
    filtered = filtered[filtered[typologie_col] == selected_typo]

if selected_classement != "Tous":
    filtered = filtered[filtered[classement_col] == selected_classement]

# =========================================================
# KPIs
# =========================================================
c1, c2, c3, c4 = st.columns(4)
c1.metric("Établissements", f"{len(filtered):,}")
c2.metric("Départements", f"{filtered['DEPT'].nunique()}")
c3.metric("Communes", f"{filtered['COMMUNE'].nunique()}")
c4.metric("Capacité inconnue", f"{(filtered['TRANCHE_CAPACITE'] == 'Inconnue').sum():,}")

# =========================================================
# CARTE CONSTANTE (toujours affichée)
# =========================================================
st.subheader("🗺️ Carte — communes restantes (selon filtres)")

if df_coords is None:
    st.info(
        "Carte indisponible : ajoute un fichier coords communes (communes_coords.csv/.xlsx) dans le dossier de app.py.\n"
        "Colonnes attendues : COMMUNE | DEPT | CODE POSTAL | LAT | LON"
    )
else:
    points = (
        filtered.groupby(["DEPT", "CODE POSTAL", "CP_KEY", "COMMUNE", "COMMUNE_KEY"])
        .size()
        .reset_index(name="Nb établissements")
    )

    pts = points.merge(df_coords, on=["DEPT", "CP_KEY", "COMMUNE_KEY"], how="left")

    # Après merge, pandas peut créer COMMUNE_x/COMMUNE_y selon les cas : on harmonise
    if "COMMUNE_x" in pts.columns:
        pts = pts.rename(columns={"COMMUNE_x": "COMMUNE"})
    if "CODE POSTAL_x" in pts.columns:
        pts = pts.rename(columns={"CODE POSTAL_x": "CODE POSTAL"})

    # Fallback : DEPT+CP uniquement
    missing = pts["LAT"].isna().sum()
    if missing > 0:
        coords_cp = (
            df_coords.drop_duplicates(subset=["DEPT", "CP_KEY"])
            .rename(columns={"LAT": "LAT_CP", "LON": "LON_CP"})
        )
        pts = pts.merge(coords_cp[["DEPT", "CP_KEY", "LAT_CP", "LON_CP"]], on=["DEPT", "CP_KEY"], how="left")
        pts["LAT"] = pts["LAT"].fillna(pts["LAT_CP"])
        pts["LON"] = pts["LON"].fillna(pts["LON_CP"])
        pts = pts.drop(columns=["LAT_CP", "LON_CP"])

    pts = pts.dropna(subset=["LAT", "LON"])

    if len(pts) == 0:
        st.warning("Aucun point cartographiable (coordonnées non trouvées après jointure).")
    else:
        m = px.scatter_mapbox(
            pts,
            lat="LAT",
            lon="LON",
            size="Nb établissements",
            hover_name="COMMUNE",
            hover_data={"CODE POSTAL": True, "DEPT": True, "Nb établissements": True},
            zoom=5,
            height=560,
        )
        m.update_layout(mapbox_style="open-street-map", margin={"l": 0, "r": 0, "t": 0, "b": 0})
        st.plotly_chart(m, use_container_width=True)

# =========================================================
# TABLE + EXPORT (la liste reste toujours affichée)
# =========================================================
st.subheader("📋 Liste filtrée")

show_cols = [c for c in [
    "NOM COMMERCIAL", "COMMUNE", "CODE POSTAL", "DEPT",
    "TYPOLOGIE ÉTABLISSEMENT", "CLASSEMENT",
    "CAPACITÉ D'ACCUEIL (PERSONNES)", "TRANCHE_CAPACITE",
    "SITE INTERNET"
] if c in filtered.columns]

st.dataframe(filtered[show_cols], use_container_width=True, height=520)

st.download_button(
    "⬇️ Export CSV (résultats filtrés)",
    data=filtered.to_csv(index=False, sep=";").encode("utf-8"),
    file_name="prospects_filtres.csv",
    mime="text/csv"
)
