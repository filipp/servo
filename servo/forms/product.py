# -*- coding: utf-8 -*-
# Copyright (c) 2013, First Party Software
# All rights reserved.

# Redistribution and use in source and binary forms, with or without modification, 
# are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice, 
# this list of conditions and the following disclaimer.

# 2. Redistributions in binary form must reproduce the above copyright notice, 
# this list of conditions and the following disclaimer in the documentation 
# and/or other materials provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE 
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE 
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE 
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR 
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT 
# OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) 
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF 
# SUCH DAMAGE.

import re
from django import forms
from django.utils.translation import ugettext as _
from django.core.exceptions import ValidationError

from servo.models import Location, User, TaggedItem
from servo.models.purchases import PurchaseOrderItem
from servo.models.product import Product, ProductCategory
from servo.forms.base import BaseModelForm, DatepickerInput, TextInput


class ProductSearchForm(forms.Form):
    title = forms.CharField(
        required=False,
        label=_('Name contains')
    )
    code = forms.CharField(
        required=False,
        label=_('Code contains')
    )
    description = forms.CharField(
        required=False,
        label=_('Description contains')
    )
    tag = forms.ModelChoiceField(
        required=False,
        label=_('Device model is'),
        queryset=TaggedItem.objects.none()
    )

    def __init__(self, *args, **kwargs):
        super(ProductSearchForm, self).__init__(*args, **kwargs)
        tags = TaggedItem.objects.filter(content_type__model="product").distinct("tag")
        self.fields['tag'].queryset = tags


class ProductUploadForm(forms.Form):
    datafile = forms.FileField(label=_("Product datafile"))
    category = forms.ModelChoiceField(
        required=False,
        queryset=ProductCategory.objects.all()
    )


class PartsImportForm(forms.Form):
    partsdb = forms.FileField(label=_("Parts database file"))
    import_vintage = forms.BooleanField(
        initial=True,
        required=False,
        label=_("Import vintage parts")
    )
    update_prices = forms.BooleanField(
        initial=True,
        required=False,
        label=_("Update product prices")
    )


class PurchaseOrderItemEditForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderItem
        exclude = ('sn',)
        widgets = {
            'product': forms.HiddenInput(),
            'code': forms.TextInput(attrs={'class': 'input-small'}),
            'amount': forms.TextInput(attrs={'class': 'input-mini'}),
            'price': forms.TextInput(attrs={'class': 'input-mini'}),
            'title': forms.TextInput(attrs={'class': 'input-xlarge'}),
        }
        localized_fields = ('price',)


class PurchaseOrderItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ('sn', 'amount',)
        localized_fields = ('price',)

    def clean(self):
        cleaned_data = super(PurchaseOrderItemForm, self).clean()
        return cleaned_data


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        exclude = ('files',)
        widgets = {
            'code': TextInput(),
            'title': TextInput(attrs={'class': 'input-xlarge'}),
            'categories': forms.CheckboxSelectMultiple(),
            'description': forms.Textarea(attrs={'class': 'span12', 'rows': 6}),
        }
        localized_fields = (
            'price_purchase_exchange',
            'pct_margin_exchange',
            'price_notax_exchange',
            'price_sales_exchange',
            'price_purchase_stock',
            'pct_margin_stock',
            'price_notax_stock',
            'price_sales_stock',
            'pct_vat',
            'shipping',
        )

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if not re.match(r'^[\w\-/]+$', code):
            raise ValidationError(_('Product code %s contains invalid characters') % code)

        return code


class CategoryForm(BaseModelForm):
    class Meta:
        model = ProductCategory
        exclude = []


class PurchaseOrderSearchForm(forms.Form):
    state = forms.ChoiceField(
        required=False,
        label=_('State is'),
        choices=(
            ('', _('Any')),
            ('open', _('Open')),
            ('submitted', _('Submitted')),
            ('received', _('Received')),
        ),
        widget=forms.Select(attrs={'class': 'input-small'})
    )
    created_by = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.filter(is_active=True)
    )
    start_date = forms.DateField(
        required=False,
        label=_('Start date'),
        widget=DatepickerInput(attrs={
            'class': "input-small",
            'placeholder': _('Start date')
        })
    )
    end_date = forms.DateField(
        required=False,
        label=_('End date'),
        widget=DatepickerInput(attrs={
            'class': "input-small",
            'placeholder': _('End date')
        })
    )
    reference = forms.CharField(
        required=False,
        label=_('Reference contains')
    )


class IncomingSearchForm(forms.Form):
    """
    A form for searching incoming products
    """
    location = forms.ModelChoiceField(
        label=_('Location is'),
        queryset=Location.objects.all(),
        widget=forms.Select(attrs={'class': 'input-medium'})
    )
    ordered_start_date = forms.DateField(
        label=_('Ordered between'),
        widget=DatepickerInput(attrs={
            'class': "input-small",
            'placeholder': _('Start date')
        })
    )
    ordered_end_date = forms.DateField(
        label='',
        widget=DatepickerInput(attrs={
            'class': "input-small",
            'placeholder': _('End date')
        })
    )
    received_start_date = forms.DateField(
        label=_('Received between'),
        widget=DatepickerInput(attrs={
            'class': "input-small",
            'placeholder': _('Start date')
        })
    )
    received_end_date = forms.DateField(
        label='',
        widget=DatepickerInput(attrs={
            'class': "input-small",
            'placeholder': _('End date')
        })
    )
    confirmation = forms.CharField(
        label=_('Confirmation is')
    )
    service_order = forms.CharField(
        label=_('Service order is')
    )

