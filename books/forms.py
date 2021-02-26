from django import forms

NUMS= [
    ('1', '1'),
    ('2', '2'),
    ('3', '3'),
    ('4', '4'),
    ]

class SearchForm(forms.Form):
    author_search = forms.CharField(label='Author', max_length=100,required = False)
    year_search = forms.CharField(label='Year',required = False,max_length=4)
    isbn_search = forms.CharField(label='ISBN', max_length=100,required = False)
    rating_search = forms.CharField(widget=forms.RadioSelect(choices=NUMS), required=False)


    