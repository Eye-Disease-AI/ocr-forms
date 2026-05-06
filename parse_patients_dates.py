import sys
import pandas as pd
from pathlib import Path

root = Path(sys.argv[1])
files = [f.stem.split('_') for f in root.glob('*/kwestionariusze/*.jpg')]
df = pd.DataFrame(files, columns=['initials', 'type', 'date'])[['initials', 'date']]
df['initials'] = df['initials'].str.upper()
df.to_csv('patients_dates.csv', index=False)
 