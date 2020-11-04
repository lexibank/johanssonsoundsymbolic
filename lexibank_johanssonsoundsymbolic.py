from pathlib import Path
import pylexibank
from clldutils.misc import slug

from openpyxl import load_workbook
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
        args.writer.add_sources()
        ref = "JohanssonEtAl2020"

        # Mapping from plain text refs to bibtex keys
        # Note: bibliography parsed by https://anystyle.io/, with very little cleaning
        with open("etc/ref_to_bib.csv", "r", encoding="utf-8") as f:
            file = csv.reader(f)
            to_bibtexkey = dict(list(file))

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

        def transpose(rows):
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
        langoids = self.glottolog.languoids_by_code()
        for language in transpose(languages_wide):
            lg_id = slug(language["Language name"])
            ref = language["Full Reference"]
            kwargs = {}
            if ref in to_bibtexkey:
                kwargs["Source"] = to_bibtexkey[ref]
            isocode = language["ISO 639-3"]
            if isocode is not None and isocode != "N/A":
                kwargs["ISO639P3code"] = isocode
            if lg_id == "allentiac":
                langoid = langoids["alle1238"]
            else:
                langoid = langoids.get(isocode, None)
            if langoid is not None:
                kwargs["Glottocode"] = langoid.glottocode
                kwargs["Latitude"] = langoid.latitude
                kwargs["Longitude"] = langoid.longitude
            args.writer.add_language(
                ID=lg_id,
                Name=language["Language name"],
                Family=language["Family name (Glottolog 2015-05-05)"],
                Macroarea=language["Geograhpical macro-area"],
                **kwargs
            )
            language_lookup[language["Language name"]] = lg_id
            # 245 languages in total !
            # Note: each language also has a Familu name according to Ethnologue, under "Family name (Ethnologue 2015-05-05)"

        # Some concepts were renamed, so we can not guess the English from the data
        with open("etc/renamed_concepts.csv", "r", encoding="utf-8") as f:
            file = csv.reader(f)
            renamed_concepts = dict(list(file))

        ## Blocks of rows separated by empty rows represent each aligned cognate group.
        # Again the forms are in wide format
        blocks = groupby(data, lambda r: r[0] is None)
        for i, (empty, forms_wide) in enumerate(blocks):
            if not empty:
                forms_wide = list(forms_wide)
                concept = forms_wide[0][0].upper()
                # No other way to recognize "FLY (N)" and "(V)", both have "fly"
                if i == 164:
                    concept = "FLY (N)"
                elif i == 166:
                    concept = "FLY (V)"
                elif concept not in concept_lookup:
                    concept = renamed_concepts[concept]
                forms_wide[0][0] = "Ortho"
                for row in transpose([header] + forms_wide):
                    if row["Ortho"] is not None \
                            and row['Present transciption system'] is not None:
                        args.writer.add_form(
                            Language_ID=language_lookup[row["Language name"]],
                            Parameter_ID=concept_lookup[concept],
                            Value=row['Ortho'],
                            Form=row['Present transciption system'],
                            # Source=[row['Source']],
                            # This is a reference, but not very systematically
                            # formatted, would require manual matching to use.
                        )
