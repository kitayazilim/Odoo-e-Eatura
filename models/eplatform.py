import logging
import json
import requests
from datetime import datetime

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

invoice_status = {
    0: 'Taslak',
    5: 'Test',
    10: 'İptal',
    20: 'Kuyrukta',
    30: 'Gönderim Bekliyor',
    40: 'Hata',
    50: 'GIB\'e İletildi',
    60: 'Onaylandı',
    61: 'Onaylanıyor',
    62: 'Onaylama Hatası',
    65: 'Otomatik Onaylama',
    70: 'Onay Bekliyor',
    80: 'Reddedildi',
    81: 'Reddediliyor',
    82: 'Reddetme Hatası',
    90: 'İade',
    91: 'İade Ediliyor',
    92: 'İade Hatası',
    99: 'e-Fatura İptal',
    100: 'e-Arşiv İptal'
}

earchive_email_status = {
    0: 'Oluşturuldu',
    10: 'Kuyrukta',
   20: 'Gönderildi',
   30: 'Hata',
   40: 'Gönderim Durdu'
}

earchive_email_type = {
    0: 'Fatura Bildirimi',
    1: 'İptal Bildirimi'
}


def j2n(param):
    return ''.join([i for i in str(param) if '0' <= i <= '9'])


def send_invoice(account, partner, lines):
    try:
        prefix, year, inv_no = account.name.split("/")
        prefix = prefix[0:3]      
        year = year[0:4]
        inv_no = inv_no.zfill(9)
        invoiceNumber = "".join([prefix, year, inv_no])
    except Exception as e:
        raise Exception("Fatura No formati hatali. Örnek: GIB2020000000001")

    name = partner.name.split()[0:-1]
    SurName = partner.name.split()[-1] if partner.name.split()[-1] else '.'

    if account.type == 'out_refund':
        refund_name = account.reversed_entry_id.name
        refund_date = account.reversed_entry_id.invoice_date.strftime(
            "%Y-%m-%dT%H:%M:%S")

    efatura_payload = {
        "recordType": account.e_recordtype,  # 0 -> e-Arşiv, 1 -> e-Fatura
        "status": 20,  # 0 -> Taslak , 20-> Kaydet ve Gönder
        "xsltCode": None,
        "localReferenceId": None,
        "useManualInvoiceId": True,
        "notes": [
            {"note": account.narration or ""}
        ],
        "addressBook": {
            "name": partner.name if len(j2n(partner.vat)) == 10 else " ".join(name),
            "receiverPersonSurName": None if len(j2n(partner.vat)) == 10 else SurName,
            # "registerNumber": "1111222243",  # tc sicil no
            "identificationNumber": j2n(partner.vat),
            "alias": getattr(partner, 'e_email', None),
            "receiverStreet": partner.street or None,
            "receiverDistrict": partner.city or None,
            "receiverZipCode": partner.zip or None,
            "receiverCity": partner.state_id.name or None,
            "receiverCountry": partner.country_id.name or None,
            "receiverPhoneNumber": partner.phone or None,
            "receiverEmail": partner.email or None,
            "receiverWebSite": getattr(partner, 'website'),
            "receiverTaxOffice": getattr(partner, 'tax_office_id.name', None)
        },
        "generalInfoModel": {
            "ettn": None,
            "prefix": "",
            "invoiceNumber": invoiceNumber,
            # Temel : 0 Ticari : 1 İhracat : 2 Yolcu Beraber : 3 EArsiv : 4 Hal Tipi Fatura :6
            "invoiceProfileType": account.digital_invoice_type,
            "issueDate": account.invoice_date.strftime("%Y-%m-%dT%H:%M:%S"),
            "issueTime": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            # Satış: 1 İade: 2 İstisna: 3 Özel Matrah: 4 Tevkifat: 5 İhraç Kayıtlı: 7 Sgk :8 Komisyoncu: 9 Hal Tipi Satış:12 Hal Tipi Komisyoncu: 13
            "type": account.e_invoicetype,
            "returnInvoiceNumber": None if account.type != 'out_refund' else refund_name,
            "returnInvoiceDate": None if account.type != 'out_refund' else refund_date,
            "currencyCode": account.currency_id.name,
            "exchangeRate": 0
        },
        "archiveInfoModel": {
            "isInternetSale": False,
            "websiteUrl": None,
            "shipmentSenderTcknVkn": None,
            "shipmentSendType": "KAGIT",
            "shipmentSenderName": None,
            "shipmentSenderSurname": None,
            "shipmentDate": None,
            "hideDespatchMessage": True,
            "subscriptionType": None,
            "subscriptionTypeNumber": None
        },
        "eArsivInfo": {
            "sendEMail": True if partner.email else False,
        },
        "ublSettingsModel": {
            "useCalculatedVatAmount": False,
            "useCalculatedTotalSummary": False
        }

    }

    data_line = []
    for line in lines:
        data = {
            'inventoryCard': line.product_id.name,
            'amount': line.quantity,
            'discountAmount': round(line.price_unit * line.quantity, 2) - line.price_subtotal,
            'lineAmount': line.price_subtotal,
            'unitCode': getattr(line.product_uom_id, 'code', "C62"),
            'unitPrice':  line.price_unit,
            'discountRate': line.discount
        }

        tax = {}
        vat_rate = None
        if line.tax_ids.amount_type == "percent":
            vat_rate = getattr(line.tax_ids, 'amount', "18")
        elif line.tax_ids.amount_type == "group" and line.tax_ids.code == "9015":
            data['taxes'] = []
            data["disableVatExemption"]: True
            taxs = line.tax_ids.children_tax_ids
            for tax in taxs:
                if tax.code:
                    tax = {
                        "taxTypeCode": line.tax_ids.code,
                        "withHoldingCode": tax.code,
                        "taxRate": tax.rate,
                        "taxAmount": round(abs(data["lineAmount"]*tax.amount)/100, 2)
                    }
                else:
                    vat_rate = tax.amount

        data["vatRate"] = vat_rate

        if tax:
            data['taxes'].append(tax)

        data_line.append(data)

    efatura_payload['invoiceLines'] = data_line
    endpoint = f"{account.company_id.ef_url}/send_invoice"
    r = requests.post(url=endpoint, json=efatura_payload,
                      auth=(account.company_id.ef_user, account.company_id.ef_password), verify=False, timeout=80)

    r.raise_for_status()
    return r.json()


def get_outbox_Pdf(account_move):
    endpoint = f"{account_move.company_id.ef_url}/get_pdf_outbox/{account_move.invoice_unique_id}/true"
    r = requests.get(url=endpoint, auth=(account_move.company_id.ef_user,
                                         account_move.company_id.ef_password), verify=False, timeout=60)
    r.raise_for_status()
    if not r.text.startswith('%PDF'):
        raise Exception(r.text)

    return r.content


def get_gib_user(self):
    endpoint = f"{self.env.company.ef_url}/get_user/{j2n(self.vat)}"
    r = requests.get(url=endpoint, auth=(self.env.company.ef_user,
                                         self.env.company.ef_password), verify=False, timeout=60)

    r.raise_for_status()

    return json.loads(r.text)


def cancel_invoice(account_move):
    endpoint = f"{account_move.company_id.ef_url}/cancelinvoice/{account_move.invoice_unique_id}"
    r = requests.get(url=endpoint, auth=(account_move.company_id.ef_user,
                                         account_move.company_id.ef_password), verify=False, timeout=60)
    r.raise_for_status()
    return


def get_inv_mdl(account_move):
    endpoint = f"{account_move.company_id.ef_url}/get_inv_mdl_bsc_outbox/{account_move.invoice_unique_id}"
    r = requests.get(url=endpoint, auth=(account_move.company_id.ef_user,
                                         account_move.company_id.ef_password), verify=False, timeout=60)

    r.raise_for_status()
    res = json.loads(r.text)

    return res


def get_email_detail(account_move):
    endpoint = f"{account_move.company_id.ef_url}/email_detail/{account_move.invoice_unique_id}"
    r = requests.get(url=endpoint, auth=(account_move.company_id.ef_user,
                                         account_move.company_id.ef_password), verify=False, timeout=60)

    r.raise_for_status()
    res = json.loads(r.text)

    msg = []
    for n in res:
        tip = earchive_email_type[n["type"]]
        durum = earchive_email_status[n["emailStatus"]]
        zaman = n["updatedDate"][0:19].replace("T", " ")
        line = f"""{zaman} {tip} {n["emailAddress"]}: {durum}"""
        msg.append(line)
    return "\n".join(msg)


def get_outbox_envelope(account_move, envelopeId):
    endpoint = f"{account_move.company_id.ef_url}/outbox_envelope/{envelopeId}"
    r = requests.get(url=endpoint, auth=(account_move.company_id.ef_user,
                                         account_move.company_id.ef_password), verify=False, timeout=60)

    r.raise_for_status()
    res = json.loads(r.text)
    return res
