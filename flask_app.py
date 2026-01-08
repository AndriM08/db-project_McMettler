import os
import git
import hmac
import hashlib
import logging
import csv
import io
from datetime import datetime, timedelta

from flask import Flask, redirect, render_template, request, url_for, flash, Response
from dotenv import load_dotenv
from flask_login import login_user, logout_user, login_required, current_user

from db import db_read, db_write
from auth import login_manager, authenticate, register_user

# ---------------- Logging ----------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ---------------- ENV ----------------
load_dotenv()
W_SECRET = os.getenv("W_SECRET", "")

# ---------------- Flask App ----------------
app = Flask(__name__)
app.config["DEBUG"] = True
app.secret_key = os.getenv("W_SECRET", "supersecret")  # besser als hardcoded

# ---------------- Auth ----------------
login_manager.init_app(app)
login_manager.login_view = "login"


# =========================
# GitHub Webhook (DON'T CHANGE)
# =========================
def is_valid_signature(x_hub_signature, data, private_key):
    hash_algorithm, github_signature = x_hub_signature.split("=", 1)
    algorithm = hashlib.__dict__.get(hash_algorithm)
    encoded_key = bytes(private_key, "latin-1")
    mac = hmac.new(encoded_key, msg=data, digestmod=algorithm)
    return hmac.compare_digest(mac.hexdigest(), github_signature)


@app.post("/update_server")
def webhook():
    x_hub_signature = request.headers.get("X-Hub-Signature")
    if x_hub_signature and is_valid_signature(x_hub_signature, request.data, W_SECRET):
        repo = git.Repo("./mysite")
        origin = repo.remotes.origin
        origin.pull()
        return "Updated PythonAnywhere successfully", 200
    return "Unauthorized", 401


# =========================
# Auth Routes
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        user = authenticate(request.form["username"], request.form["password"])
        if user:
            login_user(user)
            return redirect(url_for("index"))
        error = "Benutzername oder Passwort ist falsch."

    return render_template(
        "auth.html",
        title="In dein Konto einloggen",
        action=url_for("login"),
        button_label="Einloggen",
        error=error,
        footer_text="Noch kein Konto?",
        footer_link_url=url_for("register"),
        footer_link_label="Registrieren",
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        ok = register_user(username, password)
        if ok:
            return redirect(url_for("login"))
        error = "Benutzername existiert bereits."

    return render_template(
        "auth.html",
        title="Neues Konto erstellen",
        action=url_for("register"),
        button_label="Registrieren",
        error=error,
        footer_text="Du hast bereits ein Konto?",
        footer_link_url=url_for("login"),
        footer_link_label="Einloggen",
    )


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# =========================
# App (Ernährungsplaner)
# =========================

# ---------- Startseite (Dashboard) ----------
@app.route("/", methods=["GET"])
@login_required
def index():
    profil = db_read(
        "SELECT * FROM NutzerProfil WHERE person_id=%s",
        (current_user.id,),
        single=True,
    )
    return render_template("dashboard.html", profil=profil)


# ---------- Use Case 1: Profil ----------
def calc_kalorienbedarf(gewicht_kg: float, groesse_cm: float | None, aktivitaet: str, ziel: str) -> int:
    # sehr einfache, schul-taugliche Näherung
    aktiv_faktoren = {"niedrig": 1.2, "mittel": 1.45, "hoch": 1.7}
    a = aktiv_faktoren.get((aktivitaet or "mittel").lower(), 1.45)

    if groesse_cm is None:
        grund = gewicht_kg * 24
    else:
        grund = (gewicht_kg * 22) + (groesse_cm * 6)

    ziel_faktoren = {"bulk": 1.10, "cut": 0.85, "balanced": 1.00, "erhaltung": 1.00}
    z = ziel_faktoren.get((ziel or "balanced").lower(), 1.00)

    return int(round(grund * a * z))


@app.route("/profil", methods=["GET"])
@login_required
def profil():
    profil_row = db_read(
        "SELECT * FROM NutzerProfil WHERE person_id=%s",
        (current_user.id,),
        single=True,
    )
    # Effekte für Anzeige/Dropdown
    effekte = db_read("SELECT * FROM Effekt ORDER BY name")
    user_effekte = db_read(
        """
        SELECT e.effekt_id, e.name
        FROM Nutzer_Effekt ne
        JOIN Effekt e ON e.effekt_id = ne.effekt_id
        WHERE ne.person_id=%s
        ORDER BY e.name
        """,
        (current_user.id,),
    )
    return render_template("profil.html", profil=profil_row, effekte=effekte, user_effekte=user_effekte)


@app.route("/profil/save", methods=["POST"])
@login_required
def profil_save():
    name = request.form.get("name", "").strip()
    gewicht = request.form.get("gewicht_kg", "").strip()
    groesse = request.form.get("groesse_cm", "").strip()
    aktiv = request.form.get("aktivitaetslevel", "mittel").strip()
    ziel = request.form.get("ziel", "balanced").strip()

    if not name or not gewicht:
        flash("Bitte Name und Gewicht ausfüllen.")
        return redirect(url_for("profil"))

    try:
        gewicht_kg = float(gewicht)
        groesse_cm = float(groesse) if groesse else None
    except ValueError:
        flash("Gewicht/Grösse müssen Zahlen sein.")
        return redirect(url_for("profil"))

    kcal = calc_kalorienbedarf(gewicht_kg, groesse_cm, aktiv, ziel)

    exists = db_read(
        "SELECT person_id FROM NutzerProfil WHERE person_id=%s",
        (current_user.id,),
        single=True,
    )

    if exists:
        db_write(
            """
            UPDATE NutzerProfil
            SET name=%s, gewicht_kg=%s, kalorienbedarf=%s
            WHERE person_id=%s
            """,
            (name, gewicht_kg, kcal, current_user.id),
        )
    else:
        db_write(
            """
            INSERT INTO NutzerProfil (person_id, name, gewicht_kg, kalorienbedarf)
            VALUES (%s, %s, %s, %s)
            """,
            (current_user.id, name, gewicht_kg, kcal),
        )

    flash(f"Profil gespeichert. Kalorienbedarf: {kcal} kcal/Tag")
    return redirect(url_for("profil"))


@app.route("/profil/effekt/add", methods=["POST"])
@login_required
def profil_effekt_add():
    effekt_id = request.form.get("effekt_id")
    if not effekt_id:
        return redirect(url_for("profil"))

    # Profil muss existieren, sonst FK-Fehler
    profil_exists = db_read(
        "SELECT person_id FROM NutzerProfil WHERE person_id=%s",
        (current_user.id,),
        single=True,
    )
    if not profil_exists:
        flash("Bitte zuerst Profil speichern, bevor du Effekte zuordnest.")
        return redirect(url_for("profil"))

    # Duplikate vermeiden
    exists = db_read(
        "SELECT 1 FROM Nutzer_Effekt WHERE person_id=%s AND effekt_id=%s",
        (current_user.id, effekt_id),
        single=True,
    )
    if not exists:
        db_write(
            "INSERT INTO Nutzer_Effekt (person_id, effekt_id) VALUES (%s, %s)",
            (current_user.id, effekt_id),
        )
        flash("Effekt hinzugefügt.")
    else:
        flash("Effekt war bereits zugeordnet.")
    return redirect(url_for("profil"))


@app.route("/profil/effekt/delete", methods=["POST"])
@login_required
def profil_effekt_delete():
    effekt_id = request.form.get("effekt_id")
    if effekt_id:
        db_write(
            "DELETE FROM Nutzer_Effekt WHERE person_id=%s AND effekt_id=%s",
            (current_user.id, effekt_id),
        )
        flash("Effekt entfernt.")
    return redirect(url_for("profil"))


# ---------- Use Case 2: Lebensmittel ----------
@app.route("/lebensmittel", methods=["GET"])
@login_required
def lebensmittel():
    rows = db_read("SELECT * FROM Lebensmittel ORDER BY name")
    return render_template("lebensmittel.html", lebensmittel=rows)


@app.route("/lebensmittel/add", methods=["POST"])
@login_required
def lebensmittel_add():
    name = request.form.get("name", "").strip()
    kcal = request.form.get("kalorien_pro_100g", "").strip()
    prot = request.form.get("proteine_pro_100g", "").strip()

    if not name or not kcal or not prot:
        flash("Bitte alle Felder ausfüllen.")
        return redirect(url_for("lebensmittel"))

    try:
        float(kcal)
        float(prot)
    except ValueError:
        flash("Kalorien/Proteine müssen Zahlen sein.")
        return redirect(url_for("lebensmittel"))

    # optional: upsert by name
    exists = db_read("SELECT lebensmittel_id FROM Lebensmittel WHERE name=%s", (name,), single=True)
    if exists:
        db_write(
            "UPDATE Lebensmittel SET kalorien_pro_100g=%s, proteine_pro_100g=%s WHERE name=%s",
            (kcal, prot, name),
        )
        flash("Lebensmittel aktualisiert.")
    else:
        db_write(
            "INSERT INTO Lebensmittel (name, kalorien_pro_100g, proteine_pro_100g) VALUES (%s,%s,%s)",
            (name, kcal, prot),
        )
        flash("Lebensmittel hinzugefügt.")
    return redirect(url_for("lebensmittel"))


# ---------- Use Case 3: Gerichte + Zutaten ----------
@app.route("/gerichte", methods=["GET"])
@login_required
def gerichte():
    rows = db_read("SELECT * FROM Gericht ORDER BY name")
    return render_template("gerichte.html", gerichte=rows)


@app.route("/gerichte/add", methods=["POST"])
@login_required
def gerichte_add():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Name fehlt.")
        return redirect(url_for("gerichte"))

    exists = db_read("SELECT gericht_id FROM Gericht WHERE name=%s", (name,), single=True)
    if exists:
        flash("Gericht existiert schon.")
        return redirect(url_for("gerichte"))

    db_write("INSERT INTO Gericht (name) VALUES (%s)", (name,))
    flash("Gericht hinzugefügt.")
    return redirect(url_for("gerichte"))


@app.route("/gerichte/<int:gericht_id>", methods=["GET"])
@login_required
def gericht_detail(gericht_id):
    gericht = db_read("SELECT * FROM Gericht WHERE gericht_id=%s", (gericht_id,), single=True)
    if not gericht:
        flash("Gericht nicht gefunden.")
        return redirect(url_for("gerichte"))

    lebensmittel_rows = db_read("SELECT * FROM Lebensmittel ORDER BY name")

    zutaten = db_read(
        """
        SELECT l.lebensmittel_id, l.name, gl.menge_gramm, l.kalorien_pro_100g, l.proteine_pro_100g
        FROM Gericht_Lebensmittel gl
        JOIN Lebensmittel l ON l.lebensmittel_id = gl.lebensmittel_id
        WHERE gl.gericht_id=%s
        ORDER BY l.name
        """,
        (gericht_id,),
    )

    total_kcal = 0.0
    total_prot = 0.0
    for z in zutaten:
        menge = float(z["menge_gramm"])
        total_kcal += float(z["kalorien_pro_100g"]) * menge / 100.0
        total_prot += float(z["proteine_pro_100g"]) * menge / 100.0

    # Effekte (optional anzeigen/zuordnen)
    effekte = db_read("SELECT * FROM Effekt ORDER BY name")
    gericht_effekte = db_read(
        """
        SELECT e.effekt_id, e.name
        FROM Gericht_Effekt ge
        JOIN Effekt e ON e.effekt_id = ge.effekt_id
        WHERE ge.gericht_id=%s
        ORDER BY e.name
        """,
        (gericht_id,),
    )

    return render_template(
        "gericht_detail.html",
        gericht=gericht,
        lebensmittel=lebensmittel_rows,
        zutaten=zutaten,
        total_kcal=round(total_kcal, 1),
        total_prot=round(total_prot, 1),
        effekte=effekte,
        gericht_effekte=gericht_effekte,
    )


@app.route("/gerichte/<int:gericht_id>/zutaten/add", methods=["POST"])
@login_required
def gericht_zutat_add(gericht_id):
    lebensmittel_id = request.form.get("lebensmittel_id")
    menge = request.form.get("menge_gramm", "").strip()

    if not lebensmittel_id or not menge:
        flash("Bitte Lebensmittel und Menge angeben.")
        return redirect(url_for("gericht_detail", gericht_id=gericht_id))

    try:
        menge_val = float(menge)
        if menge_val <= 0:
            raise ValueError
    except ValueError:
        flash("Menge muss eine positive Zahl sein.")
        return redirect(url_for("gericht_detail", gericht_id=gericht_id))

    exists = db_read(
        "SELECT 1 FROM Gericht_Lebensmittel WHERE gericht_id=%s AND lebensmittel_id=%s",
        (gericht_id, lebensmittel_id),
        single=True,
    )

    if exists:
        db_write(
            "UPDATE Gericht_Lebensmittel SET menge_gramm=%s WHERE gericht_id=%s AND lebensmittel_id=%s",
            (menge_val, gericht_id, lebensmittel_id),
        )
        flash("Zutat existierte schon – Menge wurde aktualisiert.")
    else:
        db_write(
            "INSERT INTO Gericht_Lebensmittel (gericht_id, lebensmittel_id, menge_gramm) VALUES (%s,%s,%s)",
            (gericht_id, lebensmittel_id, menge_val),
        )
        flash("Zutat hinzugefügt.")

    return redirect(url_for("gericht_detail", gericht_id=gericht_id))


@app.route("/gerichte/<int:gericht_id>/effekt/add", methods=["POST"])
@login_required
def gericht_effekt_add(gericht_id):
    effekt_id = request.form.get("effekt_id")
    if not effekt_id:
        return redirect(url_for("gericht_detail", gericht_id=gericht_id))

    exists = db_read(
        "SELECT 1 FROM Gericht_Effekt WHERE gericht_id=%s AND effekt_id=%s",
        (gericht_id, effekt_id),
        single=True,
    )
    if not exists:
        db_write(
            "INSERT INTO Gericht_Effekt (gericht_id, effekt_id) VALUES (%s,%s)",
            (gericht_id, effekt_id),
        )
        flash("Effekt hinzugefügt.")
    else:
        flash("Effekt war schon zugeordnet.")
    return redirect(url_for("gericht_detail", gericht_id=gericht_id))


@app.route("/gerichte/<int:gericht_id>/effekt/delete", methods=["POST"])
@login_required
def gericht_effekt_delete(gericht_id):
    effekt_id = request.form.get("effekt_id")
    if effekt_id:
        db_write(
            "DELETE FROM Gericht_Effekt WHERE gericht_id=%s AND effekt_id=%s",
            (gericht_id, effekt_id),
        )
        flash("Effekt entfernt.")
    return redirect(url_for("gericht_detail", gericht_id=gericht_id))


# ---------- Use Case 4: Ernährungsplan generieren ----------
WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MAHLZEITEN = ["Morgen", "Mittag", "Abend"]


def parse_date(s: str):
    return datetime.strptime(s, "%Y-%m-%d").date()


@app.route("/plan", methods=["GET"])
@login_required
def plan():
    plan_rows = db_read(
        """
        SELECT ep.plan_id, ep.tag, ep.mahlzeit, g.name AS gericht, ep.von_datum, ep.bis_datum
        FROM Ernaehrungsplan ep
        JOIN Gericht g ON g.gericht_id = ep.gericht_id
        WHERE ep.person_id=%s
        ORDER BY ep.von_datum, ep.tag, ep.mahlzeit
        """,
        (current_user.id,),
    )
    return render_template("plan.html", plan=plan_rows)


@app.route("/plan/generate", methods=["POST"])
@login_required
def plan_generate():
    von = request.form.get("von_datum", "").strip()
    bis = request.form.get("bis_datum", "").strip()

    if not von or not bis:
        flash("Bitte von_datum und bis_datum angeben.")
        return redirect(url_for("plan"))

    try:
        start = parse_date(von)
        end = parse_date(bis)
    except ValueError:
        flash("Datum muss im Format YYYY-MM-DD sein.")
        return redirect(url_for("plan"))

    if end < start:
        flash("bis_datum muss nach von_datum sein.")
        return redirect(url_for("plan"))

    # Profil muss existieren für FK auf NutzerProfil
    profil_exists = db_read(
        "SELECT person_id FROM NutzerProfil WHERE person_id=%s",
        (current_user.id,),
        single=True,
    )
    if not profil_exists:
        flash("Bitte zuerst Profil speichern (Use Case 1), bevor du einen Plan generierst.")
        return redirect(url_for("profil"))

    # Effekte des Users
    effekte = db_read("SELECT effekt_id FROM Nutzer_Effekt WHERE person_id=%s", (current_user.id,))
    effekt_ids = [e["effekt_id"] for e in effekte]
    if not effekt_ids:
        flash("Bitte zuerst einen Effekt/Ziel im Profil setzen.")
        return redirect(url_for("profil"))

    placeholders = ",".join(["%s"] * len(effekt_ids))
    gerichte = db_read(
        f"""
        SELECT DISTINCT g.gericht_id, g.name
        FROM Gericht g
        JOIN Gericht_Effekt ge ON ge.gericht_id = g.gericht_id
        WHERE ge.effekt_id IN ({placeholders})
        ORDER BY g.name
        """,
        tuple(effekt_ids),
    )

    if not gerichte:
        flash("Keine passenden Gerichte gefunden. (Gericht_Effekt prüfen)")
        return redirect(url_for("plan"))

    # Alte Einträge im Zeitraum löschen (damit es nicht doppelt wird)
    db_write(
        "DELETE FROM Ernaehrungsplan WHERE person_id=%s AND von_datum=%s AND bis_datum=%s",
        (current_user.id, start, end),
    )

    created = 0
    idx = 0
    cur = start
    while cur <= end:
        tag_name = WOCHENTAGE[cur.weekday()]
        for mahlzeit in MAHLZEITEN:
            gericht = gerichte[idx % len(gerichte)]
            idx += 1
            db_write(
                """
                INSERT INTO Ernaehrungsplan (person_id, gericht_id, mahlzeit, tag, von_datum, bis_datum)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (current_user.id, gericht["gericht_id"], mahlzeit, tag_name, start, end),
            )
            created += 1
        cur += timedelta(days=1)

    flash(f"Ernährungsplan generiert: {created} Einträge.")
    return redirect(url_for("plan"))


# ---------- Use Case 5: CSV Export ----------
@app.route("/plan/export/csv", methods=["GET"])
@login_required
def plan_export_csv():
    von = request.args.get("von_datum", "").strip()
    bis = request.args.get("bis_datum", "").strip()

    if not von or not bis:
        return "Bitte von_datum und bis_datum angeben (YYYY-MM-DD).", 400

    rows = db_read(
        """
        SELECT ep.tag, ep.mahlzeit, g.name AS gericht, ep.von_datum, ep.bis_datum
        FROM Ernaehrungsplan ep
        JOIN Gericht g ON g.gericht_id = ep.gericht_id
        WHERE ep.person_id=%s AND ep.von_datum=%s AND ep.bis_datum=%s
        ORDER BY ep.tag, ep.mahlzeit
        """,
        (current_user.id, von, bis),
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Tag", "Mahlzeit", "Gericht", "Von", "Bis"])
    for r in rows:
        writer.writerow([r["tag"], r["mahlzeit"], r["gericht"], r["von_datum"], r["bis_datum"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=ernaehrungsplan.csv"},
    )


if __name__ == "__main__":
    app.run()
