from odoo import api, fields, models, _


class wzd_message_box(models.TransientModel):
    _name = "wzd.message.box"

    def get_default(self):
        if self.env.context.get("message", False):
            return self.env.context.get("message")
        return False

    name = fields.Text(string="Message", readonly=True, default=get_default)
