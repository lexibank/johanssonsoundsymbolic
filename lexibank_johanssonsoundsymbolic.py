from pathlib import Path
import attr
import pylexibank
from clldutils.misc import slug
from collections import defaultdict
from pylexibank import Lexeme, progressbar

from itertools import groupby

import csv


# Customize your basic data.
# if you need to store other data in columns than the lexibank defaults, then over-ride
# the table type (pylexibank.[Language|Lexeme|Concept|Cognate|]) and add the required columns e.g.
#
# import attr
#
# @attr.s
# class Concept(pylexibank.Concept):
#    MyAttribute1 = attr.ib(default=None)

@attr.s
class CustomLexeme(Lexeme):
    SoundClasses = attr.ib(default=None)
    Orthography = attr.ib(default=None)


class Dataset(pylexibank.Dataset):
    dir = Path(__file__).parent
    id = "johanssonsoundsymbolic"
    lexeme_class = CustomLexeme

    # register custom data types here (or language_class, lexeme_class, cognate_class):
    # concept_class = Concept

    # define the way in which forms should be handled
    form_spec = pylexibank.FormSpec(
        brackets={"(": ")"},  # characters that function as brackets
        separators=";/,",  # characters that split forms e.g. "a, b".
        missing_data=('?', '-'),  # characters that denote missing data.
        strip_inside_brackets=True,
        first_form_only=True
        # do you want data removed in brackets or not?
    )

    def cmd_download(self, args):
        self.raw_dir.download("https://osf.io/3dsn6/download",
                              "SupMaterials2_RawLinguisticForms.xlsx")
        self.raw_dir.xls2csv("SupMaterials2_RawLinguisticForms.xlsx")

    def cmd_makecldf(self, args):
        """
        Convert the raw data to a CLDF dataset.

        A `pylexibank.cldf.LexibankWriter` instance is available as `args.writer`. Use the methods
        of this object to add data.
        """
        args.writer.add_sources()
        concepts = {}
        for concept in self.conceptlists[0].concepts.values():
            c_id = "{0}-{1}".format(concept.id.split("-")[-1],
                                    slug(concept.english))
            concepts[concept.english] = c_id
            concepts[concept.english.lower()] = c_id
            
            args.writer.add_concept(
                ID=c_id,
                Concepticon_ID=concept.concepticon_id,
                Concepticon_Gloss=concept.concepticon_gloss,
                Name=concept.english,
            )
        for k, v in self.raw_dir.read_csv('renamed_concepts.csv')[1:]:
            concepts[k] = concepts[v]
            concepts[k.lower()] = concepts[v]
        languages = args.writer.add_languages(lookup_factory='Name')
        args.log.info('loaded languages')

        data = self.raw_dir.read_csv(
                'SupMaterials2_RawLinguisticForms.Blad2.csv'
                )
        sources = {k: v for k, v in self.raw_dir.read_csv('ref_to_bib.csv')}
        languages_in_row = data[0][1:]

        # correct for double fly entry
        data[670][0] = "fly1"


        # Mapping from plain text refs to bibtex keys
        # Note: bibliography parsed by https://anystyle.io/, with very little cleaning
        to_bibtexkey = {key:ref for ref,key in self.raw_dir.read_csv("ref_to_bib.csv")}
        data += [['']]
        concept = False
        for i in progressbar(range(6, 2751, 8)):
            concept = data[i][0]
            for j, language in enumerate(languages_in_row):
                value = data[i][j+1]
                if value.strip():
                    form = data[i+2][j+1].replace(' ', '_').split('/')[0]
                    classes = data[i+3][j+1]
                    
                    source = sources.get(data[5][j+1].strip(), '')
                    args.writer.add_forms_from_value(
                            Language_ID=languages[language],
                            Parameter_ID=concepts[concept],
                            Orthography=value,
                            Value=form,
                            SoundClasses=classes,
                            Source=source
                            )

