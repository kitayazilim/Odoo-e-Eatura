import sys
import logging
import json
import requests
from datetime import datetime
from requests.exceptions import RequestException

from odoo import api, fields, models, _
from odoo.http import Response, route
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
from odoo.tools import float_compare, date_utils, email_split, email_re
from odoo.tools.misc import formatLang, format_date, get_lang
from odoo.tools.float_utils import float_round, float_is_zero

from .eplatform import send_invoice, get_outbox_Pdf, get_gib_user, cancel_invoice, get_inv_mdl, get_email_detail, get_outbox_envelope


_logger = logging.getLogger(__name__)



invoice_status = [
    ('0', 'Taslak'),
    ('5', 'Test'),
    ('10', 'İptal'),
    ('20', 'Kuyrukta'),
    ('30', 'Gönderim Bekliyor'),
    ('40', 'Hata'),
    ('50', 'GIB\'e İletildi'),    
    ('60', 'Onaylandı'),
    ('61', 'Onaylanıyor'),        
    ('62', 'Onaylama Hatası'),
    ('65', 'Otomatik Onaylama'),
    ('70', 'Onay Bekliyor'),
    ('80', 'Reddedildi'),
    ('81', 'Reddediliyor'),
    ('82', 'Reddetme Hatası'),
    ('90', 'İade'),
    ('91', 'İade Ediliyor'),
    ('92', 'İade Hatası'),
    ('99', 'e-Fatura İptal'),
    ('100', 'e-Arşiv İptal')
]

earchive_email_status = [
    ('0', 'Oluşturuldu'),
    ('10', 'Kuyrukta'),
    ('20', 'Gönderildi'),
    ('30', 'Hata'),
    ('40', 'Gönderim Durdu')
]


class AccountInvoice(models.Model):
    _inherit = 'account.move'

    e_invoice_status = fields.Boolean(string='e-Fatura status ?')
    digital_invoice_type = fields.Selection(selection=[(
        '0', 'Temel Fatura'), ('1', 'Ticari Fatura')], string='Senaryo', default='0')
    e_invoicetype = fields.Selection(selection=[('1', 'Satiş'), ('2', 'İade'), (
        '5', 'Tevkifat')], string='Fatura Tipi', default='1')
    e_recordtype = fields.Selection(
        selection=[('0', 'e-Arşiv'), ('1', 'e-Fatura'), ('2', 'Kağıt')], string='Fatura Türü', default='2')
    invoice_unique_id = fields.Char(string="ETTN")    
    invoice_status_text = fields.Selection(selection=invoice_status, string="Durum")
    invoice_mail_text = fields.Selection(selection=earchive_email_status, string="e-Posta Durumu")
    inv_pdf = fields.Binary('inv_pdf', compute="_get_inv_pdf")

    @api.onchange('partner_id')
    def set_e_invoice_type(self):
        if self.partner_id.e_invoice_type in ('0', '1') and self.state == 'draft':
            self.e_recordtype = self.partner_id.e_invoice_type

    def update_status_e_inv(self, rec=None):
        try:
            rec = rec is not None and rec or self
            data = get_inv_mdl(rec)
            status = data.get('status')         
            rec.invoice_status_text =  str(status)           
            if data.get('earsivInvoice', None):
                status = data["earsivInvoice"]["eMailStatus"]
                rec.invoice_mail_text = str(status) 
        except RequestException as e:
            raise UserError(e.response.text)
        except Exception as e:
            raise UserError(str(e))

    def send_efat(self):
        try:
            if not self.e_recordtype:
                raise Exception("Fatura Türünü Seçiniz")

            if self.type not in ('out_invoice', 'out_refund'):
                raise Exception(
                    "Fatura Tipi Hatalı. Müşteri Faturası veya Müşteri İade/Fiyat Farkı Faturası olmalı")

            if self.type == 'out_refund' and self.e_invoicetype != '2':
                raise Exception("Fatura Tipini İade Seçiniz")

            responce = send_invoice(
                self, self.partner_id, self.invoice_line_ids)
            self.invoice_unique_id = responce.get('id')  # invoiceNumber
            self.message_post(body="Fatura GİB'e gönderildi",
                              subject="Fatura gönderildi")   
            self.update_status_e_inv()                           
        except RequestException as e:          
            dc =json.loads(e.response.text)           
            raise UserError("\n".join(dc['Uyarı'])) 
        except Exception as e:
            raise UserError(str(e))
       

    def _get_inv_pdf(self):
        import base64
        self.inv_pdf = base64.b64encode(
            get_outbox_Pdf(self))

    def get_efat_Pdf(self):
        if not self.invoice_unique_id:
            raise UserError("Fatura GIB'ğına aktarınız")
        return {
            'type': 'ir.actions.act_url',
            'name': 'contract',
            'url': '/web/content/account.move/%s/inv_pdf/%s.pdf' % (self.id, self.invoice_unique_id),

        }

    def cancel_e_arsiv(self):
        try:
            active_id = self._context.get('active_id')
            active_model = self._context.get('active_model')

            # Check for selected invoices ids
            if not active_id or active_model != 'account.move':
                return

            invoices = self.env['account.move'].browse(active_id)

            cancel_invoice(invoices)
            self.update_status_e_inv(invoices)
            invoices.message_post(body="Fatura iptal edildi",
                                  subject="Fatura iptal edildi")
            context = dict(self._context or {})
            context["message"] = "Fatura İptal edildi."
            return {
                'name': 'Fatura İptal',
                'type': 'ir.actions.act_window',
                'res_model': 'wzd.message.box',
                'view_mode': 'form',
                'target': 'new',
                'context': context
            }
        except RequestException as e:
            raise UserError(e.response.text)
        except Exception as e:
            raise UserError(str(e))

    def get_email_detail(self):
        try:
            self.update_status_e_inv()
            data = get_email_detail(self)
            context = dict(self._context or {})
            context["message"] = data
            return {
                'name': 'E-Posta Detayi',
                'type': 'ir.actions.act_window',
                'res_model': 'wzd.message.box',
                'view_mode': 'form',
                'target': 'new',
                'context': context
            }
        except RequestException as e:
            raise UserError(e.response.text)
        except Exception as e:
            raise UserError(str(e))

    def get_outbox_envelope(self):
        try:
            inv_mdl = get_inv_mdl(self)
            status = inv_mdl.get('status')
            self.invoice_status_text = str(status)
            data = get_outbox_envelope(self, inv_mdl['envelopeId'])
            context = dict(self._context or {})
            context["message"] = f"""{data['message']} \nZarf Kodu : {data['status']}"""
            return {
                'name': 'Hata Detayı',
                'type': 'ir.actions.act_window',
                'res_model': 'wzd.message.box',
                'view_mode': 'form',
                'target': 'new',
                'context': context
            }
        except RequestException as e:
            raise UserError(str(e))
        except Exception as e:
            raise UserError(str(e))
