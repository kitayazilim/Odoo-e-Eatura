# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    ef_url = fields.Char(string=_('URL'))
    ef_user = fields.Char(string=_('User'))
    ef_password = fields.Char(string=_('Password'))
