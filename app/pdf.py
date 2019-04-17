import PyPDF2
from app import db
from time import strptime
import re
from datetime import datetime
from flask_login import current_user
from app.models import Freight, Items

now = datetime.utcnow


def represents_int(s):
    """Check if string should be integer"""
    try:
        int(s)
        return True
    except ValueError:
        return False


def kreuger_invoice_info(lng_lst):
    """Extract Invoice number and date from PDF"""
    invoice_number = ''
    invoice_myd = ''
    for z in lng_lst:
        if 'Invoice #' in z:
            invoice_number = z.replace('Invoice # ', '')
        elif 'Invoice Date' in z:
            invoice_myd = z.replace('Invoice Date ', '')
        elif 'Credit #' in z:
            invoice_number = z.replace('Credit # ', '')
    invoice_year = invoice_myd[-4:]
    invoice_mnth = invoice_myd[:3]
    invoice_month = strptime(invoice_mnth, '%b').tm_mon
    invoice_day = invoice_myd[4:6]
    return invoice_number, invoice_myd, invoice_year, invoice_month, int(invoice_day)


def negative_val(val1):
    """Change a value to negative"""
    price1 = -float(val1)
    return price1


def define_bunch(current_list):
    """Define multiple variables for insert statement"""
    qty_fn = current_list[0]
    itm_fn = current_list[1]
    prc_fn = current_list[2].split()
    price_fn = prc_fn[0].replace('$', '')
    item_type_fn = prc_fn[1]
    price_total_raw_fn = current_list[3]
    return qty_fn, itm_fn, prc_fn, price_fn, item_type_fn, price_total_raw_fn


def no_desc_sql(invoice_no, invoice_date, year, month, day, qty, itm, item, item_type, price, price_total, taxable,
                credit, file_name):
    """SQL statement execution if no description"""
    sql_five = Items(invoice=invoice_no,
                     date=invoice_date,
                     year=year,
                     month=month,
                     day=day,
                     source='Krueger',
                     qty=qty,
                     itm=itm,
                     item=item,
                     type=item_type,
                     price=price,
                     price_total=price_total,
                     credit=credit,
                     taxable=taxable,
                     file=file_name,
                     added_by=current_user)
    db.session.add(sql_five)
    db.session.commit()


def desc_sql(c_list, invoice_no, invoice_date, year, month, day, qty, itm, item, item_type, price, price_total, taxable,
             credit, file_name):
    """SQL statement execution if description exists"""
    desc = c_list[5]
    sql_desc = Items(invoice=invoice_no,
                     date=invoice_date,
                     year=year,
                     month=month,
                     day=day,
                     source='Krueger',
                     qty=qty,
                     itm=itm,
                     item=item,
                     type=item_type,
                     price=price,
                     price_total=price_total,
                     credit=credit,
                     taxable=taxable,
                     desc=desc,
                     file=file_name,
                     added_by=current_user)
    db.session.add(sql_desc)
    db.session.commit()


def freight_sql(lng_lst, frt_index, invoice_no, invoice_date, year, month, day, file_name):
    """SQL statement for freight table"""
    freight_price = lng_lst[frt_index].replace('$', '').strip()
    sql_freight = Freight(invoice=invoice_no,
                          date=invoice_date,
                          year=year,
                          month=month,
                          day=day,
                          price=freight_price,
                          source='Krueger',
                          file=file_name,
                          added_by=current_user)
    db.session.add(sql_freight)
    db.session.commit()


def dir_loop(files_output, local_path):
    rep = {" ST": "", " BU": "", " PC": "", "'": ""}
    rep = dict((re.escape(k), v) for k, v in rep.items())
    pattern = re.compile("|".join(rep.keys()))
    rep2 = {"$": "", ",": ""}
    rep2 = dict((re.escape(g), h) for g, h in rep2.items())
    pattern2 = re.compile("|".join(rep2.keys()))
    files, pdf_path = files_output, local_path
    short_list = []
    total_items = 0
    freight_invoice = ''
    frt_index = 0
    for pdf in files:
        pdf_file_obj = open(pdf, 'rb')
        pdf_reader = PyPDF2.PdfFileReader(pdf_file_obj)
        no_of_pages = pdf_reader.getNumPages()
        pdf_text = ''
        for page in range(no_of_pages):
            page_obj = pdf_reader.getPage(page)
            pdf_text += page_obj.extractText()
        long_list = pdf_text.splitlines()
        for index, line in enumerate(long_list):
            if 'Freight' in line:
                frt_index = index + 1
        if 'Invoice #' in long_list[4]:
            short_list = long_list[16:-15]
        elif 'Credit #' in long_list:
            short_list = long_list[16:-9]
        invoice_no, invoice_date, year, month, day = kreuger_invoice_info(long_list)
        name_check = [1]
        markers = []
        for index, line in enumerate(short_list):
            if represents_int(line) and (index - name_check[-1] != 1):
                markers.append(index)
                name_check.append(index)
        mark_first = markers[:-1]
        mark_last = markers[1:]
        file_name = pdf[len(pdf_path) + 1:-len('.pdf')]
        for x, y in zip(mark_first, mark_last):
            cur_list = short_list[x:y]
            qty, itm, prc, price, item_type, price_total_raw = define_bunch(cur_list)
            price_total = pattern2.sub(lambda m: rep2[re.escape(m.group(0))], price_total_raw)
            taxable = False
            credit = False
            if 'T' in cur_list[3]:
                taxable = True
                price_total = price_total.replace('T', '')
            if "Credit Invoice" in long_list[3]:
                price, price_total = negative_val(price), negative_val(price_total)
                credit = True
            name_list = list(filter(None, cur_list[4].split('  ')))
            item_long = name_list[0]
            item = pattern.sub(lambda m: rep[re.escape(m.group(0))], item_long)
            if y - x == 5:
                total_items += 1
                no_desc_sql(invoice_no, invoice_date, year, month, day, qty, itm, item, item_type, price,
                            price_total, taxable, credit, file_name)
            elif y-x == 6:
                total_items += 1
                desc_sql(cur_list, invoice_no, invoice_date, year, month, day, qty, itm, item, item_type, price,
                         price_total, taxable, credit, file_name)
            if "Freight" in long_list and file_name != freight_invoice:
                freight_invoice = file_name
                freight_sql(long_list, frt_index, invoice_no, invoice_date, year, month, day, file_name)
        pdf_file_obj.close()
