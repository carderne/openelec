# test.sh
#!/bin/bash

# convert the example notebook to a script
jupyter nbconvert --to script example.ipynb

# remove plt.show() calls
sed -i -e 's/plt.show()/pass/g' example.py

# activate virtualenv if present but continue anyway
source /home/chris/.envs/openelec/bin/activate # || true

# run pytest
#python3 -m pytest openelec

# run script
python example.py

# clean up
rm example.py
rm -r test_output