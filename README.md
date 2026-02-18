# Budget Exceedance Explanation Tracker

Simple Flask app to collect subcontractor budget exceedance explanations via Excel uploads, assign to trades, and allow reviewer comments.

Quick start

1. Create a virtual environment and activate it (Windows):

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r "requirements.txt"
```

3. Run the app:

```powershell
python app.py
```

4. Open http://127.0.0.1:5000

Notes
- Upload an Excel file containing the sheets: `Reason`, `Qty`, `BoQ Sheet`, `Ratebrekdown` (sheet names are flexible).
- The app parses all sheets and stores the data as JSON for reviewers.
- This is an initial scaffold; features like authentication, per-trade incharge assignment UI, deadline reminders, and validation can be added next.
