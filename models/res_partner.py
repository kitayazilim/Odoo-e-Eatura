import sys
import logging
import json
import requests

from werkzeug import urls

from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.modules import get_module_resource
from odoo.osv.expression import get_unaccent_wrapper
from odoo.exceptions import UserError, ValidationError
from .eplatform import get_gib_user


class ResPartner(models.Model):
    _inherit = 'res.partner'
    e_invoice_type = fields.Selection(
        selection=[('-1', 'Kağit'), ('0', 'e-Arşiv'), ('1', 'e-Fatura')], string='Fatura Türü')
    e_email = fields.Char(string='e-Fatura Posta Kutusu')

    @api.onchange('e_invoice_type')
    def set_erecordtype(self):
        try:
            gib_user = get_gib_user(self)
            inbox = gib_user.get('receiverboxAliases', [])
            self.e_email = [
                alias.get('alias') for alias in inbox if alias.get('appType') == 1][0]
        except:
            pass
