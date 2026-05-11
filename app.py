# app.py
import csv
import difflib
import io
import random
import re
from collections import deque
from io import StringIO

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Question Section Builder", layout="wide")
st.title("Question Section Builder")

REQUIRED_COLUMNS = [
    "Question ID",
    "Question Topic",
    "Question Difficulty",
    "Question Pool",
    "Course Tag of Question",
    "Module Tag of Question",
    "Unit Tag of Question",
    "Extra Tags",
]


# -------------------------
# Helpers
# -------------------------
def normalize_text(x) -> str:
    return str(x).strip() if pd.notna(x) else ""


def parse_section_from_topic(topic: str) -> str:
    t = normalize_text(topic).upper()
    if t.endswith("_MCQ"):
        return "MCQ"
    if t.endswith("_CODING"):
        return "SQL Coding"
    return "Other"


def parse_difficulty(diff: str) -> str:
    d = normalize_text(diff).upper().replace("DIFFICULTY_", "")
    return d.title() if d else "Unknown"


def split_extra_tags(extra_tags: str):
    if pd.isna(extra_tags):
        return []
    return [x.strip().upper() for x in str(extra_tags).split(",") if x.strip()]


def get_library(extra_tags: str) -> str:
    tags = split_extra_tags(extra_tags)
    if "IS_PRIVATE" in tags:
        return "My Questions"
    if "IS_PUBLIC" in tags:
        return "Topin Questions"
    return "Unknown"


def get_set_order(extra_tags: str) -> int:
    return 0 if "SET_1" in split_extra_tags(extra_tags) else 1


def add_prefix(values: list[str], prefix: str) -> list[str]:
    p = f"{prefix}_"
    out = []
    for v in values:
        vv = normalize_text(v)
        if not vv:
            continue
        out.append(vv if vv.upper().startswith(p.upper()) else f"{p}{vv}")
    return out


def strip_prefix(values: list[str], prefix: str) -> list[str]:
    p = f"{prefix}_"
    out = []
    for v in values:
        vv = normalize_text(v)
        out.append(vv[len(p):] if vv.upper().startswith(p.upper()) else vv)
    return out


def suggest_closest_tags(selected_prefixed: list[str], available_prefixed: list[str]) -> dict[str, str]:
    suggestions = {}
    avail_u = {x.upper(): x for x in available_prefixed}
    for s in selected_prefixed:
        if s.upper() in avail_u:
            continue
        m = difflib.get_close_matches(s, available_prefixed, n=1, cutoff=0.65)
        if m:
            suggestions[s] = m[0]
    return suggestions


def read_uploaded_file(file_obj) -> pd.DataFrame:
    if file_obj is None:
        raise ValueError("No file uploaded.")
    if hasattr(file_obj, "size") and file_obj.size == 0:
        raise ValueError("Uploaded file is empty (0 bytes).")

    name = normalize_text(getattr(file_obj, "name", "")).lower()
    if name.endswith(".xlsx"):
        d = pd.read_excel(file_obj)
        if d is None or d.shape[1] == 0:
            raise ValueError("Excel has no readable columns.")
        return d

    raw = file_obj.getvalue() or b""
    if not raw:
        try:
            file_obj.seek(0)
            raw = file_obj.read()
        except Exception:
            raw = b""

    if not raw:
        raise ValueError("Uploaded file is empty (no bytes found).")

    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        for sep in (",", "\t", None):
            try:
                text = raw.decode(enc, errors="replace")
                if not text.strip():
                    continue
                d = pd.read_csv(StringIO(text), sep=sep, engine="python", on_bad_lines="skip")
                if d is not None and d.shape[1] > 0:
                    return d
            except Exception:
                pass

    raise ValueError("Could not parse uploaded file.")


def extract_question_tag(extra_tags: str) -> str:
    for t in split_extra_tags(extra_tags):
        if t.startswith("QUESTION_"):
            return t
    return ""


def extract_question_id_from_extra(extra_tags: str) -> str:
    txt = normalize_text(extra_tags)
    m = re.search(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        txt,
    )
    return m.group(0) if m else ""


def build_unique_key(row) -> str:
    if row["Question Tag"]:
        return row["Question Tag"]
    if row["Extra Question ID"]:
        return row["Extra Question ID"]
    return row["Question ID"]


def get_display_qid(row) -> str:
    return normalize_text(row.get("Extra Question ID")) or normalize_text(row.get("Question ID"))


def pick_questions_random_diverse(
    df_pool: pd.DataFrame,
    total_needed: int,
    selected_tags: list[str],
    diff_order: list[str] | None,
    random_seed: int | None,
) -> pd.DataFrame:
    if total_needed <= 0 or df_pool.empty:
        return df_pool.iloc[0:0].copy()

    rng = random.Random(random_seed)
    work = df_pool.copy()
    sc = [c for c in ["Set Order", "Question ID"] if c in work.columns]
    if sc:
        work = work.sort_values(sc)

    buckets: dict[str, deque] = {}
    if diff_order:
        for tag in selected_tags:
            tu = tag.upper()
            for diff in diff_order:
                sub = work[
                    (work["Tag"].str.upper() == tu)
                    & (work["Difficulty Parsed"].str.upper() == diff.upper())
                ]
                idx = sub.index.tolist()
                rng.shuffle(idx)
                buckets[f"{tu}||{diff.upper()}"] = deque(idx)
    else:
        for tag in selected_tags:
            tu = tag.upper()
            sub = work[work["Tag"].str.upper() == tu]
            idx = sub.index.tolist()
            rng.shuffle(idx)
            buckets[tu] = deque(idx)

    picked: list = []
    last_base: str | None = None

    while len(picked) < total_needed:
        keys = [k for k, q in buckets.items() if len(q) > 0]
        if not keys:
            break

        if last_base and len(keys) > 1:
            bases = {k.split("||")[0] if "||" in k else k for k in keys}
            if len(bases) > 1:
                alt = [k for k in keys if (k.split("||")[0] if "||" in k else k) != last_base]
                if alt:
                    keys = alt

        pk = rng.choice(keys)
        picked.append(buckets[pk].popleft())
        last_base = pk.split("||")[0] if "||" in pk else pk

    return df_pool.loc[picked].copy()


def do_pick(pool, n, tags, diffs, use_random_spread, random_seed):
    if n <= 0 or pool.empty:
        return pool.iloc[0:0].copy()
    if use_random_spread:
        return pick_questions_random_diverse(pool, n, tags, diffs, random_seed)
    return pool.head(n)


# -------------------------
# Filtering pools
# -------------------------
def filter_mcq_pool(df_all, course_full, wanted_units, include_sets):
    w = df_all[df_all["Course Tag of Question"].str.upper() == course_full.upper()].copy()
    w = w[(w["Section Derived"] == "MCQ") & (w["Question Library"] == "Topin Questions")]
    w = w[w["Unit Tag of Question"].str.upper().isin([x.upper() for x in wanted_units])]
    w["Tag"] = w["Unit Tag of Question"]
    w = w.drop_duplicates(subset=["Question ID", "Tag", "Difficulty Parsed"], keep="first")

    if not include_sets:
        w["Unique Key"] = w.apply(build_unique_key, axis=1)
        w = (
            w.sort_values(["Tag", "Difficulty Parsed", "Set Order", "Question ID"])
            .drop_duplicates(subset=["Tag", "Difficulty Parsed", "Unique Key"], keep="first")
        )
    return w


def filter_coding_pool(df_all, course_full, wanted_modules, include_sets):
    w = df_all[df_all["Course Tag of Question"].str.upper() == course_full.upper()].copy()
    w = w[(w["Section Derived"] == "SQL Coding") & (w["Question Library"] == "My Questions")]
    w = w[w["Module Tag of Question"].str.upper().isin([x.upper() for x in wanted_modules])]
    w["Tag"] = w["Module Tag of Question"]
    w = w.drop_duplicates(subset=["Question ID", "Tag", "Difficulty Parsed"], keep="first")

    if not include_sets:
        w["Unique Key"] = w.apply(build_unique_key, axis=1)
        w = (
            w.sort_values(["Tag", "Difficulty Parsed", "Set Order", "Question ID"])
            .drop_duplicates(subset=["Tag", "Difficulty Parsed", "Unique Key"], keep="first")
        )
    return w


# -------------------------
# Row-wise output (1 row per question)
# -------------------------
def build_pool_map(work: pd.DataFrame) -> dict:
    grp = (
        work.groupby(["Tag", "Difficulty Parsed", "Question Library"], dropna=False)
        .size()
        .reset_index(name="pool")
    )
    m = {}
    for _, r in grp.iterrows():
        m[(r["Tag"], r["Difficulty Parsed"], r["Question Library"])] = int(r["pool"])
    return m


def build_mcq_rows_per_question(picked: pd.DataFrame, work: pd.DataFrame) -> pd.DataFrame:
    if picked.empty:
        return pd.DataFrame()

    pool_map = build_pool_map(work)
    rows = []
    p = picked.copy()
    p["qid_display"] = p.apply(get_display_qid, axis=1)

    for _, r in p.iterrows():
        key = (r["Tag"], r["Difficulty Parsed"], r["Question Library"])
        rows.append(
            {
                "Question Library": r["Question Library"],
                "Topic": "SQL",
                "Difficulty Level": r["Difficulty Parsed"],
                "Sub Topic": "",
                "Exclusive Tags": r["Tag"],
                "Exclusive Tags-2": r["qid_display"],
                "Number of Questions": 1,
                "pool": pool_map.get(key, 0),
            }
        )

    return pd.DataFrame(rows).reset_index(drop=True)


def build_coding_rows_per_question(
    picked: pd.DataFrame,
    work: pd.DataFrame,
    marks_easy: int,
    marks_medium: int,
    marks_hard: int,
    show_question_id: bool,
) -> pd.DataFrame:
    if picked.empty:
        return pd.DataFrame()

    def marks_for_diff(diff: str) -> int:
        d = normalize_text(diff).lower()
        if d == "easy":
            return int(marks_easy)
        if d == "hard":
            return int(marks_hard)
        return int(marks_medium)

    pool_map = build_pool_map(work)
    rows = []
    p = picked.copy()
    p["qid_display"] = p.apply(get_display_qid, axis=1)

    for _, r in p.iterrows():
        key = (r["Tag"], r["Difficulty Parsed"], r["Question Library"])
        rows.append(
            {
                "Question Library": r["Question Library"],
                "Topic": "SQL Coding",
                "Difficulty Level": r["Difficulty Parsed"],
                "Sub Topic": "",
                "Exclusive Tags": r["Tag"],
                "Question Tag": normalize_text(r.get("Question Tag", "")),
                "Exclusive Tags-2": r["qid_display"] if show_question_id else "",
                "Number of Questions": 1,
                "Marks for Each Question": marks_for_diff(r["Difficulty Parsed"]),
                "pool": pool_map.get(key, 0),
            }
        )

    return pd.DataFrame(rows).reset_index(drop=True)


def build_dual_section_formatted_csv(mcq_df: pd.DataFrame, coding_df: pd.DataFrame) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")

    # MCQ block
    w.writerow(["Section Type", "MCQ"])
    w.writerow(["Name of section", "MCQs"])
    w.writerow(["Time Limit (in Mins)", "30"])
    w.writerow(
        [
            "Question Library",
            "Topic",
            "Difficulty Level",
            "Sub Topic",
            "Exclusive Tags",
            "Exclusive Tags-2",
            "Number of Questions",
            "pool",
        ]
    )
    if mcq_df is not None and not mcq_df.empty:
        for _, r in mcq_df.iterrows():
            w.writerow(
                [
                    r["Question Library"],
                    r["Topic"],
                    r["Difficulty Level"],
                    r["Sub Topic"],
                    r["Exclusive Tags"],
                    r["Exclusive Tags-2"],
                    r["Number of Questions"],
                    r["pool"],
                ]
            )

    w.writerow([])

    # Coding block
    w.writerow(["Section Type", "SQL"])
    w.writerow(["Name of the section", "SQL Coding"])
    w.writerow(["Time Limit (in Mins)", "45"])
    w.writerow(
        [
            "Question Library",
            "Topic",
            "Difficulty Level",
            "Sub Topic",
            "Exclusive Tags",
            "Question Tag",
            "Exclusive Tags-2",
            "Number of Questions",
            "Marks for Each Question",
            "pool",
        ]
    )
    if coding_df is not None and not coding_df.empty:
        for _, r in coding_df.iterrows():
            w.writerow(
                [
                    r["Question Library"],
                    r["Topic"],
                    r["Difficulty Level"],
                    r["Sub Topic"],
                    r["Exclusive Tags"],
                    r["Question Tag"],
                    r["Exclusive Tags-2"],
                    r["Number of Questions"],
                    r["Marks for Each Question"],
                    r["pool"],
                ]
            )

    return buf.getvalue()


# -------------------------
# UI: Upload
# -------------------------
uploaded = st.file_uploader("Step 1: Upload CSV/TSV/XLSX", type=["csv", "txt", "xlsx"])
if uploaded is None:
    st.info("Upload a file to continue.")
    st.stop()

st.write(f"Uploaded: `{uploaded.name}` | Size: `{uploaded.size}` bytes")

try:
    df = read_uploaded_file(uploaded)
except Exception as e:
    st.error(f"Could not read file: {e}")
    st.stop()

df.columns = df.columns.astype(str).str.replace("\ufeff", "", regex=False).str.strip()
for col in REQUIRED_COLUMNS:
    if col not in df.columns:
        df[col] = ""
for col in REQUIRED_COLUMNS:
    df[col] = df[col].apply(normalize_text)

df["Section Derived"] = df["Question Topic"].apply(parse_section_from_topic)
df["Difficulty Parsed"] = df["Question Difficulty"].apply(parse_difficulty)
df["Question Library"] = df["Extra Tags"].apply(get_library)
df["Set Order"] = df["Extra Tags"].apply(get_set_order)
df["Question Tag"] = df["Extra Tags"].apply(extract_question_tag)
df["Extra Question ID"] = df["Extra Tags"].apply(extract_question_id_from_extra)

st.success(f"File loaded. Rows: {len(df)}")

course_tags = strip_prefix(sorted([x for x in df["Course Tag of Question"].unique() if x]), "COURSE")
unit_tags = strip_prefix(sorted([x for x in df["Unit Tag of Question"].unique() if x]), "UNIT")
module_tags = strip_prefix(sorted([x for x in df["Module Tag of Question"].unique() if x]), "MODULE")

st.subheader("Step 2: Available Tags")
c1, c2, c3 = st.columns(3)
with c1:
    st.dataframe(pd.DataFrame({"Course Tag": course_tags}), use_container_width=True, height=200)
with c2:
    st.dataframe(pd.DataFrame({"Unit Tag": unit_tags}), use_container_width=True, height=200)
with c3:
    st.dataframe(pd.DataFrame({"Module Tag": module_tags}), use_container_width=True, height=200)

# -------------------------
# UI: Inputs
# -------------------------
st.subheader("Step 3: Create Section")

SECTION_OPTIONS = [("MCQ", "MCQ"), ("Coding", "Coding"), ("Both", "MCQ and Coding")]
section_choice = st.selectbox(
    "Section",
    options=[x[0] for x in SECTION_OPTIONS],
    format_func=lambda k: dict(SECTION_OPTIONS)[k],
)

course_input = st.selectbox(
    "Course (without COURSE_)",
    options=course_tags if course_tags else [""],
    index=0,
)

include_sets = st.checkbox(
    "With sets (unchecked = unique questions for both MCQ and Coding)",
    value=False,
)
use_random_spread = st.checkbox("Random + spread across units/modules", value=True)
seed_val = st.number_input("Random seed (0 = different each run)", min_value=0, value=0, step=1)
random_seed = None if seed_val == 0 else int(seed_val)

if section_choice in ("Coding", "Both"):
    st.write("Marks for coding questions")
    m1, m2, m3 = st.columns(3)
    with m1:
        marks_easy = st.number_input("Easy marks", min_value=0, value=10, step=1)
    with m2:
        marks_medium = st.number_input("Medium marks", min_value=0, value=20, step=1)
    with m3:
        marks_hard = st.number_input("Hard marks", min_value=0, value=30, step=1)
else:
    marks_easy = marks_medium = marks_hard = 0

selected_units: list[str] = []
selected_modules: list[str] = []
total_mcq = 0
ce = cm = ch = 0

if section_choice == "MCQ":
    selected_units = st.multiselect("Units (without UNIT_)", options=unit_tags)
    total_mcq = st.number_input("Total MCQ questions", min_value=1, value=10, step=1)
elif section_choice == "Coding":
    selected_modules = st.multiselect("Modules (without MODULE_)", options=module_tags)
    x1, x2, x3 = st.columns(3)
    with x1:
        ce = st.number_input("Easy", min_value=0, value=1, step=1)
    with x2:
        cm = st.number_input("Medium", min_value=0, value=1, step=1)
    with x3:
        ch = st.number_input("Hard", min_value=0, value=1, step=1)
else:
    selected_units = st.multiselect("Units for MCQ (without UNIT_)", options=unit_tags)
    selected_modules = st.multiselect("Modules for Coding (without MODULE_)", options=module_tags)
    total_mcq = st.number_input("Total MCQ questions", min_value=1, value=5, step=1)
    st.write("Coding difficulty counts")
    x1, x2, x3 = st.columns(3)
    with x1:
        ce = st.number_input("Easy", min_value=0, value=1, step=1)
    with x2:
        cm = st.number_input("Medium", min_value=0, value=1, step=1)
    with x3:
        ch = st.number_input("Hard", min_value=0, value=1, step=1)

generate = st.button("Generate Output", type="primary")
if not generate:
    st.stop()

if not normalize_text(course_input):
    st.error("Select a course.")
    st.stop()

course_full = f"COURSE_{course_input}"

mcq_rows = pd.DataFrame()
coding_rows = pd.DataFrame()

# -------------------------
# Build MCQ
# -------------------------
if section_choice in ("MCQ", "Both"):
    if not selected_units:
        st.error("Select at least one unit for MCQ.")
        st.stop()

    wanted_u = add_prefix(selected_units, "UNIT")
    pool_mcq = filter_mcq_pool(df, course_full, wanted_u, include_sets=include_sets)

    sug = suggest_closest_tags(
        wanted_u,
        sorted(pool_mcq["Unit Tag of Question"].dropna().astype(str).unique().tolist()),
    )
    if sug:
        st.warning("Some units are not exact matches:")
        st.json(sug)

    picked_mcq = do_pick(pool_mcq, int(total_mcq), wanted_u, None, use_random_spread, random_seed)

    if len(picked_mcq) < int(total_mcq):
        st.warning(f"MCQ: requested {total_mcq}, got {len(picked_mcq)}.")

    mcq_rows = build_mcq_rows_per_question(picked_mcq, pool_mcq)

# -------------------------
# Build Coding
# -------------------------
if section_choice in ("Coding", "Both"):
    if not selected_modules:
        st.error("Select at least one module for Coding.")
        st.stop()

    coding_total_req = int(ce + cm + ch)
    if coding_total_req == 0:
        st.error("Set at least one coding question (Easy/Medium/Hard).")
        st.stop()

    wanted_m = add_prefix(selected_modules, "MODULE")
    pool_cd = filter_coding_pool(df, course_full, wanted_m, include_sets=include_sets)

    sug = suggest_closest_tags(
        wanted_m,
        sorted(pool_cd["Module Tag of Question"].dropna().astype(str).unique().tolist()),
    )
    if sug:
        st.warning("Some modules are not exact matches:")
        st.json(sug)

    parts = []
    for diff, need in (("Easy", ce), ("Medium", cm), ("Hard", ch)):
        need = int(need)
        if need <= 0:
            continue
        sub = pool_cd[pool_cd["Difficulty Parsed"].str.upper() == diff.upper()]
        parts.append(do_pick(sub, need, wanted_m, [diff], use_random_spread, random_seed))

    picked_cd = pd.concat(parts, ignore_index=False) if parts else pool_cd.iloc[0:0]

    if len(picked_cd) < coding_total_req:
        st.warning(f"Coding: requested {coding_total_req}, got {len(picked_cd)}.")

    coding_rows = build_coding_rows_per_question(
        picked_cd,
        pool_cd,
        marks_easy,
        marks_medium,
        marks_hard,
        show_question_id=(not include_sets),
    )

# -------------------------
# Display
# -------------------------
st.subheader("Step 4: Output")

if section_choice == "MCQ":
    if mcq_rows.empty:
        st.warning("No MCQ rows.")
    else:
        st.markdown("**Section Type:** MCQ  \n**Name of section:** MCQs  \n**Time Limit (in Mins):** 30")
        st.dataframe(mcq_rows, use_container_width=True)
    st.download_button(
        "Download MCQ CSV",
        data=mcq_rows.to_csv(index=False).encode("utf-8"),
        file_name="mcq_section.csv",
        mime="text/csv",
    )

elif section_choice == "Coding":
    if coding_rows.empty:
        st.warning("No Coding rows.")
    else:
        st.markdown("**Section Type:** SQL  \n**Name of the section:** SQL Coding  \n**Time Limit (in Mins):** 45")
        st.dataframe(coding_rows, use_container_width=True)
    st.download_button(
        "Download Coding CSV",
        data=coding_rows.to_csv(index=False).encode("utf-8"),
        file_name="coding_section.csv",
        mime="text/csv",
    )

else:
    st.markdown("### Formatted output (MCQ + SQL Coding)")
    st.markdown("**MCQ** — Section Type: MCQ | Name: MCQs | Time: 30 min")
    st.dataframe(mcq_rows if not mcq_rows.empty else pd.DataFrame(), use_container_width=True)

    st.markdown("---")
    st.markdown("**SQL Coding** — Section Type: SQL | Name: SQL Coding | Time: 45 min")
    st.dataframe(coding_rows if not coding_rows.empty else pd.DataFrame(), use_container_width=True)

    formatted = build_dual_section_formatted_csv(mcq_rows, coding_rows)
    st.text_area("Preview (formatted CSV)", formatted, height=320)
    st.download_button(
        "Download formatted CSV (MCQ block + SQL block)",
        data=formatted.encode("utf-8"),
        file_name="mcq_and_coding_formatted.csv",
        mime="text/csv",
    )