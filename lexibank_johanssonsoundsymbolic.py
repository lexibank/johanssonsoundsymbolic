from pathlib import Path
import pylexibank
from clldutils.misc import slug

from openpyxl import load_workbook
from pycldf import Source
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


class Dataset(pylexibank.Dataset):
    dir = Path(__file__).parent
    id = "johanssonsoundsymbolic"

    # register custom data types here (or language_class, lexeme_class, cognate_class):
    # concept_class = Concept

    # define the way in which forms should be handled
    form_spec = pylexibank.FormSpec(
        brackets={"(": ")"},  # characters that function as brackets
        separators=";/,",  # characters that split forms e.g. "a, b".
        missing_data=('?', '-'),  # characters that denote missing data.
        strip_inside_brackets=True
        # do you want data removed in brackets or not?
    )

    def cmd_download(self, args):
        """
        Download files to the raw/ directory. You can use helpers methods of `self.raw_dir`, e.g.
        to download a temporary TSV file and convert to persistent CSV:

        >>> with self.raw_dir.temp_download("http://www.example.com/e.tsv", "example.tsv") as data:
        ...     self.raw_dir.write_csv('template.csv', self.raw_dir.read_csv(data, delimiter='\t'))
        """
        self.raw_dir.download("https://osf.io/3dsn6/download",
                              "SupMaterials2_RawLinguisticForms.xlsx")

    def cmd_makecldf(self, args):
        """
        Convert the raw data to a CLDF dataset.

        A `pylexibank.cldf.LexibankWriter` instance is available as `args.writer`. Use the methods
        of this object to add data.
        """
        data_source = Source("article", "JohanssonEtAl2020",
                             author="Niklas Erben Johansson "
                                    "and Andrey Anikin and "
                                    "Gerd Carling and Arthur Holmer",
                             title="The typology of sound symbolism: "
                                   "Defining macro-concepts via their "
                                   "semantic and phonetic features",
                             journal="Linguistic Typology",
                             year="01 Jul. 2020",
                             publisher="De Gruyter Mouton",
                             address="Berlin, Boston",
                             volume="24",
                             number="2",
                             doi="https://doi.org/10.1515/lingty-2020-2034",
                             pages="253 - 310",
                             url="https://www.degruyter.com/view"
                                 "/journals/lity/24/2/article-p253.xml"
                             )
        args.writer.add_sources(data_source)

        concept_lookup = {}
        for concept in self.conceptlists[0].concepts.values():
            c_id = "{0}-{1}".format(concept.id.split("-")[-1],
                                    slug(concept.english))
            concept_lookup[concept.english] = c_id
            args.writer.add_concept(
                ID=c_id,
                Concepticon_ID=concept.concepticon_id,
                Concepticon_Gloss=concept.concepticon_gloss,
                Name=concept.english,
            )

        def data_iterator(data):
            """Iterate on rows as lists of values.
            Ignores the last 50 cells (always None).
            """
            for row in data:
                yield [cell.value for cell in row][:-50]

        def pivot_table(rows):
            """Takes a table in wide form as a list of list and serves it in long form as dicts.

            rows: a list of lists of values. The first element of each inner list is the index of the row.

            """
            index = [r[0] for r in rows]
            rows_long = zip(*[r[1:] for r in rows])
            for cells in rows_long:
                yield dict(zip(index, cells))

        excel = load_workbook("raw/SupMaterials2_RawLinguisticForms.xlsx",
                              read_only=True)
        data = data_iterator(excel['Blad2'].rows)

        ## Languages are the first six rows in the table, wide format.
        languages_wide = [next(data) for _ in range(6)]
        header = languages_wide[0]
        language_lookup = {}
        for language in pivot_table(languages_wide):
            lg_id = slug(language["Language name"])
            args.writer.add_language(
                ID=lg_id,
                ISO639P3code=language["ISO 639-3"],
                Family=language["Family name (Glottolog 2015-05-05)"],
                Macroarea=language["Geograhpical macro-area"]
            )
            language_lookup[language["Language name"]] = lg_id
            # 245 languages in total !
            # Note: each language also has a full text citation under "Full Reference", do these need to go into the sources ?
            # Note: each language also has a Familu name according to Ethnologue, under "Family name (Ethnologue 2015-05-05)"


        # Some concepts were renamed, so we can not guess the English from the data
        with open("etc/renamed_concepts.csv", "r", encoding="utf-8") as f:
            file = csv.reader(f)
            renamed_concepts = dict(list(file))

        ## Blocks of rows separated by empty rows represent each aligned cognate group.
        # Again the forms are in wide format
        for i, (empty,  forms_wide) in enumerate(groupby(data, lambda r:r[0] is None)):
            if not empty:
                forms_wide = list(forms_wide)
                concept = forms_wide[0][0].upper()
                if i == 164: # No other way to recognize these, they both have "FLY"
                    concept = "FLY (N)"
                elif i == 166:
                     concept = "FLY (V)"
                elif concept not in concept_lookup:
                    concept = renamed_concepts[concept]

                forms_wide[0][0] = "Ortho" # This changes for each concept, we need a consistent header
                for row in pivot_table([header] + forms_wide):
                    if row["Ortho"] is not None \
                            and row['Present transciption system'] is not None:
                        args.writer.add_form(
                                     Language_ID=language_lookup[row["Language name"]],
                                     Parameter_ID=concept_lookup[concept],
                                     Value=row['Ortho'],
                                     Form=row['Present transciption system'],
                            #         Source=[row['Source']],
                            )