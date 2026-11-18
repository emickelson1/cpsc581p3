from better_profanity import Profanity # https://pypi.org/project/better-profanity/
from pathlib import Path

POLITICAL_CSV_PATH = Path(__file__).resolve().parent.parent / "resources" / "political_terms.csv"
REPLACEMENTS = {
    '.' : '',   # e.g. "James K. Polk"
    '-' : ' ',  # e.g. "Bill A-12"
    '/' : ' ',  # e.g. "9/11"
    '\'': ' '   # e.g. "O'Reilly"
}

def parse(csvpath: str) -> list[str]:
    terms = set()
    with open(csvpath, 'r') as f:
        f.readline()
        for line in f.readlines():
            term     = line.split(',')[0]
            # category = line.split(',')[1]
            
            # clean up term
            term = term.lower()
            for k in REPLACEMENTS.keys():
                term = term.replace(k, REPLACEMENTS[k])
                
            # split names and add each to list
            # if category == "Politicians & Public Figures":
            #     for name in term.split(' '): terms.add(name) # because "Kamala" should get filtered even if only "Kamala Harris" is in the list
            # else:
            
            terms.add(term)
    return sorted(list(terms))


# profanity words
profanity = Profanity()
profanity.load_censor_words() # default profanity filter

# political words
political = Profanity()
political.add_censor_words(parse(str(POLITICAL_CSV_PATH)))


def filter(input: str) -> tuple[bool, str]:
    if profanity.contains_profanity(input): return True, "profanity"
    if political.contains_profanity(input): return True, "political"
    else: return False, ""


def main():
    # Test on an input
    query = input("Test the profanity/political filter on an input: ")
    filtered, reason = filter(query)
    censored = profanity.censor(political.censor(query))
    print(f"Filtered:\t{filtered}\nReason:\t\t{reason}\nCleaned:\t{censored}")


if __name__ == "__main__":
    main()