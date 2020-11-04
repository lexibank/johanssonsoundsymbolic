from setuptools import setup
import json


with open('metadata.json', encoding='utf-8') as fp:
    metadata = json.load(fp)


setup(
    name='lexibank_johanssonsoundsymbolic',
    description=metadata['title'],
    license=metadata.get('license', ''),
    url=metadata.get('url', ''),
    py_modules=['lexibank_johanssonsoundsymbolic'],
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'lexibank.dataset': [
            'johanssonsoundsymbolic=lexibank_johanssonsoundsymbolic:Dataset',
        ]
    },
    install_requires=[
        'pylexibank>=2.7.2',
    ],
    extras_require={
        'test': [
            'pytest-cldf',
        ],
    },
)
