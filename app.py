from flask import Flask, render_template, request, send_file, redirect
import mysql.connector
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io

app = Flask(__name__)
import os
import qrcode
from reportlab.lib.utils import ImageReader
PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "http://localhost:5000"
)


# ---------------- DATABASE CONFIG ----------------
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASS = 'Darshan@2003'
DB_NAME = 'invoice_db'

def get_next_invoice_no():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # CHANGE 1: Select the invoice_no, order by ID (or created_at) DESC, limit to 1
    # This ensures you get the most recently inserted row, regardless of the number's value.
    cur.execute("SELECT invoice_no FROM invoices ORDER BY id DESC LIMIT 1")
    
    result = cur.fetchone()
    conn.close()
    
    # CHANGE 2: Logic to handle the increment
    if result:
        last_invoice_no = result[0]
        # Convert to int, add 1, convert back to string
        return str(int(last_invoice_no) + 1)
    else:
        return "1"


def init_db():
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS
    )
    cur = conn.cursor()

    # Create DB
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    cur.execute(f"USE {DB_NAME}")

    # INVOICES TABLE (HEADER)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    invoice_no VARCHAR(50) UNIQUE NOT NULL,
    invoice_date DATE NOT NULL,

    -- NEW ADDRESS FIELDS
    to_address TEXT NOT NULL,
    ship_to_address TEXT NULL,

    base_amount DECIMAL(10,2) NOT NULL,
    cgst_amount DECIMAL(10,2) NOT NULL,
    sgst_amount DECIMAL(10,2) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    wo_number VARCHAR(50),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

    """)

    # INVOICE ITEMS TABLE (LINE ITEMS)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            invoice_id INT NOT NULL,
            description TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (invoice_id)
                REFERENCES invoices(id)
                ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME
    )

# ---------------- PDF GENERATION ----------------
def generate_invoice_pdf(data):
    # ---- BANK DETAILS (ACTUAL / MASKED SUPPORT) ----
    account_no = data.get("account_no", "375901010032777")
    ifsc_code = data.get("ifsc", "UBIN0537594")
    invoice_id = data.get("invoice_id")


    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    left, right = 40, width - 40
    top, bottom = height - 40, 40

    # Outer Border
    c.rect(left, bottom, right - left, top - bottom)

    # ---------------- HEADER ----------------
        # ---------------- QR CODE ----------------
    invoice_id = data["invoice_id"]

    qr_url = f"{PUBLIC_BASE_URL}/invoice/{invoice_id}/pdf"

    qr = qrcode.make(qr_url)
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer)
    qr_buffer.seek(0)

    c.drawImage(
        ImageReader(qr_buffer),
        right - 120,   # X position (right side)
        top - 100,     # Y position (empty space)
        width=80,
        height=80,
        mask='auto'
    )
    c.setFont("Helvetica", 7)
    c.drawCentredString(right - 80, top - 110, "Scan to Download")


    c.setFont("Helvetica-Bold", 14)
    c.drawString(left + 10, top - 30, "GURUKRUPA EARTHMOVERS")

    c.setFont("Helvetica", 9)
    c.drawString(left + 10, top - 48,
                 "735 A PLOT NO 86, ATHANI ROAD BHIRAV NAGAR VIJAYAPUR - 586101")
    c.drawString(left + 10, top - 62,
                 "Taluk: Dist: Vijayapura | Mobile: 9448025191")
    c.drawString(left + 10, top - 76,
                 "Email: gcmukund@gmail.com")

    # TAX INVOICE
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, top - 105, "TAX INVOICE")

    # Invoice Meta (BELOW TAX INVOICE)
    meta_x = right - 210
    meta_y = top - 130

    c.setFont("Helvetica", 9)
    c.drawString(meta_x, meta_y,        f"Date: {data['invoice_date']}")
    c.drawString(meta_x, meta_y - 14,   f"Invoice No.: {data['invoice_no']}")
    c.drawString(meta_x, meta_y - 28, f"WO Number: {data['wo_number']}")
    c.drawString(meta_x, meta_y - 42,   "Our PAN No: AHSPC4247N")
    c.drawString(meta_x, meta_y - 56,   "Our GST No: 29AHSPC4247N1ZP")

    # Separator
    c.line(left, meta_y - 70, right, meta_y - 70)

    # ---------------- TO / SHIP TO ----------------
    box_top = meta_y - 70
    box_bottom = box_top - 120
    # ---------------- TO / SHIP TO ----------------
    box_height = 110
    mid = width / 2

    has_ship_to = bool(data.get("ship_to_address"))

    # Draw outer box
    c.rect(left, box_top - box_height, right - left, box_height)

    # Draw middle divider ONLY if Ship To exists
    if has_ship_to:
        c.line(mid, box_top, mid, box_top - box_height)

    # ---------- TO ----------
    c.setFont("Helvetica-Bold", 9)
    c.drawString(left + 8, box_top - 15, "To,")

    c.setFont("Helvetica", 9)
    y = box_top - 30
    for line in data['to_address'].splitlines():
        c.drawString(left + 8, y, line)
        y -= 14

    # ---------- SHIP TO (OPTIONAL) ----------
    if has_ship_to:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(mid + 8, box_top - 15, "(Ship To)")

        c.setFont("Helvetica", 9)
        y = box_top - 30
        for line in data['ship_to_address'].splitlines():
            c.drawString(mid + 8, y, line)
            y -= 14

    # ---------------- MAIN TABLE ----------------
    table_top = box_bottom
    table_bottom = table_top - 260

    col_sl = left + 50
    col_desc = right - 120

    c.rect(left, table_bottom, right - left, table_top - table_bottom)
    c.line(col_sl, table_top, col_sl, table_bottom)
    c.line(col_desc, table_top, col_desc, table_bottom)

    # Header Row
    c.line(left, table_top - 25, right, table_top - 25)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString((left + col_sl) / 2, table_top - 18, "SL No")
    c.drawCentredString((col_sl + col_desc) / 2, table_top - 18, "Description")
    c.drawCentredString((col_desc + right) / 2, table_top - 18, "Total Amount")

    # Item
# ----- ROW LAYOUT CONFIG -----
    row_height = 30        # visual row height (matches your image)
    font_size = 9
    baseline_adjust = 8   # fine-tune if needed

    # Start FIRST row exactly below header line
    row_top = table_top - 25

    for i, (desc, amt) in enumerate(zip(data['descriptions'], data['amounts']), start=1):
        # Calculate vertical center for text
        text_y = row_top - (row_height / 2) + (font_size / 2) - baseline_adjust

        c.setFont("Helvetica", font_size)

        # SL No
        c.drawCentredString((left + col_sl) / 2, text_y, str(i))

        # Description
        c.drawString(col_sl + 8, text_y, desc)

        # Amount
        c.drawRightString(right - 10, text_y, f"{amt:.2f}")

        # Draw bottom border of the row
        c.line(left, row_top - row_height, right, row_top - row_height)

        # Move to next row
        row_top -= row_height




    # ---------------- TAX ROWS ----------------
# ---------------- TAX ROWS (MATCHING SCANNED INVOICE) ----------------

    tax_start_y = table_bottom + 120
    row_gap = 22

    def tax_row(label, value, y, bold=False, size=9):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)

        # Horizontal line across TOTAL AMOUNT column
        c.line(col_desc, y + 12, right, y + 12)

        # Label just LEFT of the Total Amount column (right aligned)
        c.drawRightString(col_desc - 10, y, label)

        # Amount inside Total Amount column (right aligned)
        c.drawRightString(right - 10, y, f"{value:.2f}")


    tax_row("CGST @ 9%", data['cgst_amount'], tax_start_y)
    tax_row("SGST @ 9%", data['sgst_amount'], tax_start_y - row_gap)
    tax_row("Sub Total", data['total_amount'], tax_start_y - row_gap * 2, bold=True)

    # GRAND TOTAL
    tax_row("GRAND TOTAL", data['total_amount'],
            tax_start_y - row_gap * 3, bold=True, size=10)

    # ---------------- BANK DETAILS ----------------
    # ---------------- BANK DETAILS LOGIC ----------------
    wo_number = data.get("wo_number")

    if wo_number == "6000000055":
        bank_name = "HDFC Bank"
        account_no = "50200092531586"
        ifsc = "HDFC0001961"
        branch = "BIJAPUR"
    else:
        bank_name = "Union Bank of India"
        account_no = data.get("account_no", "375901010032777")
        ifsc = data.get("ifsc", "UBIN0537594")
        branch = "BLDE Road Vijayapur"

    # ---------------- BANK DETAILS ----------------
    bank_y = table_bottom - 20

    c.setFont("Helvetica-Bold", 9)
    c.drawString(left + 10, bank_y, "Our Bank Details:")

    c.setFont("Helvetica", 9)
    c.drawString(left + 10, bank_y - 14, f"Account No: {account_no}")
    c.drawString(left + 10, bank_y - 28, f"Bank Name: {bank_name}")
    c.drawString(left + 10, bank_y - 42, f"Branch: {branch}")
    c.drawString(left + 10, bank_y - 56, f"IFSC Code: {ifsc}")



    # ---------------- SIGNATURE ----------------
    sign_y = bank_y - 90
    
    c.setFont("Helvetica", 9)
    c.drawString(right - 165, sign_y - 35,
                 "Authorized Signatory")

   # ---------------- FOOTER NOTE (INSIDE BOX) ----------------

    note_y = bottom + 5   # inside the box, above bottom border

    c.setFont("Helvetica", 8)
    c.drawString(
        left + 10,
        note_y,
        "Note: Please make payment by Transfer/Cheque/DD in favor of "
        "Shri Mukund G Chouthai proprietor of Gurukrupa Earthmovers."
    )


    c.save()
    buffer.seek(0)
    return buffer

# ---------------- ROUTES ----------------
@app.route('/')
def index():
    next_invoice_no = get_next_invoice_no()
    return render_template('index.html', invoice_no=next_invoice_no)

@app.route('/invoice/<int:invoice_id>/pdf')
def download_invoice_pdf(invoice_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # 1️⃣ Fetch invoice header (NOW INCLUDES ADDRESSES)
    cur.execute("""
        SELECT *
        FROM invoices
        WHERE id = %s
    """, (invoice_id,))
    invoice = cur.fetchone()

    if not invoice:
        conn.close()
        return "Invoice not found", 404

    # 2️⃣ Fetch invoice items
    cur.execute("""
        SELECT description, amount
        FROM invoice_items
        WHERE invoice_id = %s
        ORDER BY id ASC
    """, (invoice_id,))
    items = cur.fetchall()

    conn.close()

    if not items:
        return "No items found for this invoice", 400

    # 3️⃣ Prepare data for PDF
    descriptions = [item['description'] for item in items]
    amounts = [float(item['amount']) for item in items]

    pdf = generate_invoice_pdf({
        "invoice_id": invoice['id'],
        "invoice_no": invoice['invoice_no'],
        "invoice_date": invoice['invoice_date'],

        # ✅ NEW ADDRESS FIELDS
        "to_address": invoice['to_address'],
        "ship_to_address": invoice['ship_to_address'],

        # ITEMS
        "descriptions": descriptions,
        "amounts": amounts,

        # TOTALS
        "base_amount": float(invoice['base_amount']),
        "cgst_amount": float(invoice['cgst_amount']),
        "sgst_amount": float(invoice['sgst_amount']),
        "total_amount": float(invoice['total_amount']),
        "wo_number": invoice['wo_number']

    })

    return send_file(
        pdf,
        as_attachment=True,
        download_name=f"Invoice_{invoice['invoice_no']}.pdf",
        mimetype="application/pdf"
    )




@app.route('/edit/<int:invoice_id>', methods=['GET', 'POST'])
def edit_invoice(invoice_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        invoice_no = request.form['invoice_no']
        invoice_date = request.form['invoice_date']

        # ✅ ADDRESSES
        to_address = request.form['to_address']
        ship_to_address = request.form.get('ship_to_address') or None

        # ITEMS
        descriptions = request.form.getlist('description[]')
        amounts = request.form.getlist('amount[]')

        if not descriptions or not amounts:
            conn.close()
            return "No invoice items provided", 400

        amounts = [float(a) for a in amounts]

        # 🔢 RECALCULATE TOTALS
        base_amount = round(sum(amounts), 2)
        cgst = round(base_amount * 0.09, 2)
        sgst = round(base_amount * 0.09, 2)
        total = round(base_amount + cgst + sgst, 2)

        # 1️⃣ UPDATE INVOICE HEADER (INCLUDING ADDRESSES)
        cur.execute("""
            UPDATE invoices SET
                invoice_no = %s,
                invoice_date = %s,
                to_address = %s,
                ship_to_address = %s,
                base_amount = %s,
                cgst_amount = %s,
                sgst_amount = %s,
                total_amount = %s
            WHERE id = %s
        """, (
            invoice_no,
            invoice_date,
            to_address,
            ship_to_address,
            base_amount,
            cgst,
            sgst,
            total,
            invoice_id
        ))

        # 2️⃣ REMOVE OLD ITEMS
        cur.execute("DELETE FROM invoice_items WHERE invoice_id = %s", (invoice_id,))

        # 3️⃣ INSERT UPDATED ITEMS
        for desc, amt in zip(descriptions, amounts):
            cur.execute("""
                INSERT INTO invoice_items (invoice_id, description, amount)
                VALUES (%s, %s, %s)
            """, (invoice_id, desc, amt))

        conn.commit()
        conn.close()
        return redirect('/history')

    # ---------------- GET REQUEST ----------------

    # FETCH INVOICE HEADER
    cur.execute("SELECT * FROM invoices WHERE id = %s", (invoice_id,))
    invoice = cur.fetchone()

    if not invoice:
        conn.close()
        return "Invoice not found", 404

    # FETCH ITEMS
    cur.execute("""
        SELECT id, description, amount
        FROM invoice_items
        WHERE invoice_id = %s
        ORDER BY id ASC
    """, (invoice_id,))
    items = cur.fetchall()

    conn.close()

    return render_template(
        'edit.html',
        invoice=invoice,
        items=items
    )




@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        # ---------------- FORM DATA ----------------
        invoice_no = request.form['invoice_no']
        invoice_date = request.form['invoice_date']

        descriptions = request.form.getlist('description[]')
        amounts = request.form.getlist('amount[]')

        to_address = request.form['to_address']
        ship_to_address = request.form.get('ship_to_address')
        wo_number = request.form['wo_number']


        # ---------------- VALIDATION ----------------
        if not descriptions or not amounts:
            return "No invoice items provided", 400

        if len(descriptions) != len(amounts):
            return "Mismatch in invoice items", 400

        # Convert amounts to float safely
        try:
            amounts = [float(a) for a in amounts]
        except ValueError:
            return "Invalid amount value", 400

        # ---------------- CALCULATIONS ----------------
        base_amount = round(sum(amounts), 2)
        cgst = round(base_amount * 0.09, 2)
        sgst = round(base_amount * 0.09, 2)
        total = round(base_amount + cgst + sgst, 2)

        # ---------------- DATABASE ----------------
        conn = get_db_connection()
        cur = conn.cursor()

        # INSERT INVOICE HEADER
        cur.execute("""
            INSERT INTO invoices
            (invoice_no, invoice_date, to_address, ship_to_address,
             base_amount, cgst_amount, sgst_amount, total_amount,wo_number)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            invoice_no,
            invoice_date,
            to_address,
            ship_to_address,
            base_amount,
            cgst,
            sgst,
            total,
            wo_number
        ))

        invoice_id = cur.lastrowid

        # INSERT LINE ITEMS
        for desc, amt in zip(descriptions, amounts):
            cur.execute("""
                INSERT INTO invoice_items
                (invoice_id, description, amount)
                VALUES (%s,%s,%s)
            """, (invoice_id, desc, amt))

        conn.commit()
        conn.close()

        # ---------------- REDIRECT (PRG PATTERN) ----------------
        # Redirect to PDF download (GET request)
        return redirect(f"/invoice/{invoice_id}/pdf")

    except mysql.connector.errors.IntegrityError:
        # Duplicate invoice number protection
        return "Invoice number already exists", 400

    except Exception as e:
        return f"Error occurred: {e}", 500



@app.route('/history')
def history():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            i.id,
            i.invoice_no,
            i.invoice_date,
            i.base_amount,
            i.cgst_amount,
            i.sgst_amount,
            i.total_amount,
            COUNT(it.id) AS item_count
        FROM invoices i
        LEFT JOIN invoice_items it
            ON i.id = it.invoice_id
        GROUP BY i.id
        ORDER BY CAST(i.invoice_no AS UNSIGNED) DESC
    """)

    invoices = cur.fetchall()
    conn.close()

    return render_template('history.html', invoices=invoices)

@app.route('/invoice/<int:invoice_id>/masked-pdf')
def download_masked_invoice_pdf(invoice_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # 1️⃣ Fetch invoice header
    cur.execute("""
        SELECT *
        FROM invoices
        WHERE id = %s
    """, (invoice_id,))
    invoice = cur.fetchone()

    if not invoice:
        conn.close()
        return "Invoice not found", 404

    # 2️⃣ Fetch invoice items
    cur.execute("""
        SELECT description, amount
        FROM invoice_items
        WHERE invoice_id = %s
        ORDER BY id ASC
    """, (invoice_id,))
    items = cur.fetchall()

    conn.close()

    if not items:
        return "No items found for this invoice", 400

    # 3️⃣ Prepare item lists
    descriptions = [item['description'] for item in items]
    amounts = [float(item['amount']) for item in items]

    # 4️⃣ Generate MASKED PDF
    pdf = generate_invoice_pdf({
        "invoice_no": invoice['invoice_no'],
        "invoice_date": invoice['invoice_date'],

        # ✅ Addresses (NOT masked)
        "to_address": invoice['to_address'],
        "ship_to_address": invoice['ship_to_address'],

        # Items
        "descriptions": descriptions,
        "amounts": amounts,

        # Totals
        "base_amount": float(invoice['base_amount']),
        "cgst_amount": float(invoice['cgst_amount']),
        "sgst_amount": float(invoice['sgst_amount']),
        "total_amount": float(invoice['total_amount']),

        # 🔒 MASKED BANK DETAILS ONLY
        "account_no": "XXXXXXXX2777",
        "ifsc": "UBIN0XXXXX"
    })

    return send_file(
        pdf,
        as_attachment=True,
        download_name=f"Invoice_{invoice['invoice_no']}_MASKED.pdf",
        mimetype="application/pdf"
    )

@app.route('/delete/<int:invoice_id>', methods=['POST'])
def delete_invoice(invoice_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Delete invoice (items auto-delete via ON DELETE CASCADE)
    cur.execute("DELETE FROM invoices WHERE id = %s", (invoice_id,))

    conn.commit()
    conn.close()

    return redirect('/history')



if __name__ == '__main__':
    init_db()
    app.run(debug=True)
