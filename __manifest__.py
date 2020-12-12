# -*- coding: utf-8 -*-
{
    'name': 'SK Turkcell E-Fatura',
    'version': '13.0.1.0.0',
    'author': 'Softteknik, Kitayazilim',
    'category': 'Accounting & Finance',
    'summary': 'Turkcell e-Şirket altyapısi ile e-Fatura, e-Arşiv Fatura hizmeti sunulmaktadır',
    'description': """
        Turkcell e-Şirket altyapısi ile e-Fatura, e-Arşiv Fatura hizmeti sunulmaktadır.
        Destek İçin destek@kitayazilim.com
    """,
    'depends': ['account', 'uom'],
    'data': [
        'data/e_invoice_uom.xml',
        'wizard/wzd_message_box.xml',
        'wizard/wzd_cancel_invoice.xml',        
        'views/product_uom_views.xml',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'views/account_invoice_views.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
