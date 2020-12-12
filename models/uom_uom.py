# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductUOM(models.Model):
    _inherit = 'uom.uom'

    code = fields.Char(size=4)
