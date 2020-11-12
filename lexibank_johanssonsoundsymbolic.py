from pathlib import Path
import attr
import pylexibank
from clldutils.misc import slug
from pylexibank import Lexeme, progressbar

@attr.s
class CustomLexeme(Lexeme):
    SoundClasses = attr.ib(default=None)
    Orthography = attr.ib(default=None)


class Dataset(pylexibank.Dataset):
    dir = Path(__file__).parent
    id = "johanssonsoundsymbolic"
    lexeme_class = CustomLexeme

    # register custom data types here (or languge_class, lexeme_class, cognate_class):
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

        concepts = args.writer.add_concepts(
            id_factory=lambda x: x.id.split("-")[-1] + "_" + slug(x.english),
            lookup_factory=lambda concept: concept.attributes["lexibank_gloss"]
        )
        languages = args.writer.add_languages(lookup_factory='Name')
        args.log.info('loaded languages')

        data = self.raw_dir.read_csv(
                'SupMaterials2_RawLinguisticForms.Blad2.csv'
                )
        sources = {k: v for k, v in self.raw_dir.read_csv('ref_to_bib.csv')}
        languages_in_row = data[0][1:]

        # correct for double fly entry
        data[670][0] = "fly1"

        data += [['']]
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

