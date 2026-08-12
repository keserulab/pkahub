# <img height="35" alt="logo" src="https://github.com/user-attachments/assets/b16786e3-4bb5-4b37-842d-b3f1806bb6ba" /> pKahub
Welcome to pKahub, the largest online collection of experimental pKa data for small molecules, 
systematically annotated with macroscopic charge state transitions.


## Usage

pKahub is hosted at: [pkahub.ttk.hu](http://pkahub.ttk.hu).


See the [About page](http://pkahub.ttk.hu/about) for information on core purpose and methodology. 

## Setting up new database
create conda/mamba environment and install the packages in requirements.txt<br>
then run:
```
python manage.py makemigrations
python manage.py migrate
python manage.py setupdb
```

## 💬 Feedback

We welcome community testing and feedback. To share observations about performance or suggestions for new features, please reach out via [email](mailto:pkahub@ttk.hu).

## Citation
  
If you use pKahub in your research, please cite our paper:

Levente Sipos-Szabó, Dávid Bajusz, György T. Balogh, György M. Keserű; Benchmarking pKa Prediction Algorithms against an Extensive, Public Data Set. J. Chem. Inf. Model. 27 April 2026; 66 (8): 4607–4619. https://doi.org/10.1021/acs.jcim.6c00107

