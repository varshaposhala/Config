# Question Section Builder 🧩

A Streamlit-based intelligent tool that reads a question bank (CSV/TSV/XLSX) and automatically generates structured assessment section configurations — with smart filtering, difficulty-aware selection, fuzzy tag matching, and randomized question distribution.

---

## 🚀 Features

- **Multi-format file support** — Accepts `.csv`, `.tsv`, `.txt`, and `.xlsx` question bank files
- **Smart tag parsing** — Automatically detects Course, Unit, Module, and Exclusive tags from raw question data
- **Section types** — Generate MCQ-only, Coding-only, or combined MCQ + Coding section configs
- **Difficulty-aware selection** — Specify exact counts for Easy, Medium, and Hard coding questions
- **Random + diverse spread** — Optional randomised selection that distributes questions across units/modules for variety
- **Fuzzy tag suggestions** — Warns users when selected tags don't exactly match available ones and suggests the closest match
- **Set deduplication** — Option to include or exclude question sets, with deduplication by Question ID and tags
- **Dynamic marks configuration** — Custom marks for Easy, Medium, and Hard coding questions
- **Auto section naming** — Section names are derived automatically from dominant topic labels in the selected questions
- **Formatted CSV export** — Outputs a ready-to-use CSV with MCQ and Coding blocks, matching the expected portal import format
- **Debug panel** — Expandable view of topic detection logic for transparency

---

## 🗂️ Project Structure

```
Config/
└── app.py      # Single-file Streamlit application (~820 lines)
```

---

## 📋 Prerequisites

- Python 3.10+
- pip

---

## ⚙️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/varshaposhala/Config.git
   cd Config
   ```

2. **Install dependencies**
   ```bash
   pip install streamlit pandas openpyxl
   ```

3. **Run the app**
   ```bash
   streamlit run app.py
   ```

---

## 📄 Input File Format

The tool expects a question bank CSV/XLSX with the following columns:

| Column | Description |
|---|---|
| `Question ID` | Unique identifier for the question |
| `Question Topic` | Topic tag (e.g., `TOPIC_SQL_MCQ`, `TOPIC_PYTHON_CODING`) |
| `Question Difficulty` | Difficulty level (`Easy`, `Medium`, `Hard`) |
| `Question Pool` | Pool identifier |
| `Course Tag of Question` | Course tag (e.g., `COURSE_DATA_SCIENCE`) |
| `Module Tag of Question` | Module tag (e.g., `MODULE_PANDAS`) |
| `Unit Tag of Question` | Unit tag (e.g., `UNIT_NUMPY`) |
| `Extra Tags` | Comma-separated tags including `IS_PUBLIC`, `IS_PRIVATE`, `SET_1`, `QUESTION_<uuid>` |

### Tag Conventions

| Tag | Meaning |
|---|---|
| `IS_PUBLIC` | Question belongs to the **Topin Questions** (public) library |
| `IS_PRIVATE` | Question belongs to **My Questions** (private) library |
| `SET_1` | Question is part of a set (used for set inclusion/exclusion) |
| `QUESTION_<uuid>` | UUID-based question identifier for precise targeting |

---

## 🖥️ How to Use

### Step 1 — Upload File
Upload your question bank CSV, TSV, or XLSX file.

### Step 2 — Review Available Tags
The app displays all detected **Course**, **Unit**, and **Module** tags.

### Step 3 — Configure Section
Choose a section type and fill in the parameters:

| Setting | Description |
|---|---|
| **Section** | MCQ, Coding, or Both |
| **Course** | Select the target course |
| **With Sets** | Include/exclude duplicate set questions |
| **Random + Spread** | Enable diverse randomised selection |
| **Random Seed** | Fix the seed for reproducible outputs (0 = different each run) |
| **Units** | Select units for MCQ section |
| **Modules** | Select modules for Coding section |
| **MCQ Count** | Total number of MCQ questions |
| **Easy / Medium / Hard** | Number of coding questions per difficulty |
| **Marks** | Marks per difficulty level for coding questions |

### Step 4 — Generate & Download
Click **Generate Output** to preview the section configuration and download the formatted CSV.

---

## 📦 Output Format

The exported CSV has two blocks separated by a blank row:

```
Section Type,MCQ
Name of section,SQL MCQs
Time Limit (in Mins),30
Question Library,Topic,Difficulty Level,Sub Topic,Exclusive Tags,Exclusive Tags-2,Number of Questions,pool
Topin Questions,SQL,Easy,,UNIT_SQL,<question_id>,1,45
...

Section Type,SQL
Name of the section,SQL Coding
Time Limit (in Mins),45
Question Library,Topic,Difficulty Level,Sub Topic,Exclusive Tags,Question Tag,Exclusive Tags-2,Number of Questions,Marks for Each Question,pool
My Questions,SQL Coding,Medium,,MODULE_SQL,question_<uuid>,,1,20,12
...
```

This output is compatible with the **Assessment Architect** portal import tool.

---

## 🔧 Core Logic Summary

| Function | Purpose |
|---|---|
| `read_uploaded_file` | Multi-encoding, multi-separator file parser |
| `display_topic_from_question_topic` | Converts raw topic tags into human-readable labels |
| `section_kind_from_question_topic` | Determines if a question is MCQ or Coding from its topic tag |
| `pick_questions_random_diverse` | Randomised, diversity-aware question picker using bucket-based round-robin |
| `suggest_closest_tags` | Fuzzy tag matching using `difflib` |
| `build_dual_section_formatted_csv` | Generates the final portal-ready CSV |

---

## 🤝 Related Project

This tool works in tandem with [**Assessment Architect (Config-Generator)**](https://github.com/varshaposhala/Config-Generator), which takes the CSV output from this tool and automatically fills it into the assessment portal via browser automation.

**Workflow:**
```
Question Bank (CSV/XLSX)
        ↓
Question Section Builder  ← this repo
        ↓
  Formatted Config CSV
        ↓
  Assessment Architect    ← Config-Generator repo
        ↓
  Portal Auto-filled ✅
```

---

## 📃 License

This project is open source. See the repository for details.
