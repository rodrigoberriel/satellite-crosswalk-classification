# Deep Learning Based Large-Scale Automatic Satellite Crosswalk Classification
High-resolution satellite imagery have been increasingly used on remote sensing classification problems. One of the main factors is the availability of this kind of data. Even though, very little effort has been placed on the zebra crossing classification problem. In this letter, crowdsourcing systems are exploited in order to enable the automatic acquisition and annotation of a large-scale satellite imagery database for crosswalks related tasks. Then, this dataset is used to train deep-learning-based models in order to accurately classify satellite images that contains or not zebra crossings. A novel dataset with more than 240,000 images from 3 continents, 9 countries and more than 20 cities were used in the experiments. Experimental results showed that freely available crowdsourcing data can be used to accurately (96.78%) train robust models to perform crosswalk classification on a global scale.

---

This repository will be used to share the data described in the paper submitted to the [Special Stream](http://www.grss-ieee.org/letters/special-streams/stream9) of the **IEEE Geoscience and Remote Sensing Letters** related to the [SIBGRAPI 2017](http://sibgrapi2017.ic.uff.br/call-grsl.html).


### Dataset Automatic Acquisition and Annotation
To download the dataset, you should run the command below for each region of interest. Be careful with your API quota.

```python
python crosswalk-downloader.py region_name {download_crosswalk:0,1} {download_no_crosswalk:0,1} API_KEY
# e.g. to download the crosswalks of the regions in Asia
python crosswalk-downloader.py asia 1 0 {API_KEY}
```

### Dataset
The dataset used in this work is defined by a group of city-based regions. As stated in the paper, "even though each
part of the dataset is named after a city, some selected regions were large enough to partially include neighboring towns". The regions can be seen in the file `regions.json` and a summary of the dataset can be seen below.

| Dataset Name               | Crosswalks | No-Crosswalks |
|----------------------------|------------|---------------|
| Europe-Belgium-Brussels    | 7,916      | 18,739        |
| Europe-France-Lion         | 5,168      | 11,960        |
| Europe-France-Paris        | 5,828      | 13,353        |
| Europe-France-Marseille    | 2,615      | 6,668         |
| Europe-France-Toulouse     | 4,794      | 11,046        |
| Europe-Italy-Turim         | 5,081      | 11,324        |
| Europe-Italy-Milan         | 4,536      | 10,147        |
| Europe-Portugal-Porto      | 1,630      | 3,786         |
| Europe-Portugal-Lisbon     | 1,731      | 4,460         |
| Europe-Spain-Saragoca      | 1,413      | 3,310         |
| Europe-Switzerland-Zurich  | 1,842      | 4,668         |
| **Europe**                 | **42,554** | **99,461**    |
| America-USA-Seattle        | 1,276      | 2,929         |
| America-USA-WashingtonDC   | 2,838      | 6,503         |
| America-USA-Philadelphia   | 2,356      | 6,145         |
| America-USA-NewYork        | 2,191      | 4,919         |
| America-Canada-Mississauga | 3,259      | 7,463         |
| America-Canada-Toronto     | 3,902      | 8,852         |
| **America**                | **15,822** | **36,811**    |
| Asia-Japan-Tokyo           | 6,888      | 15,529        |
| Asia-Japan-Toyokawa        | 1,837      | 4,140         |
| Asia-Japan-Sapporo         | 6,946      | 15,780        |
| **Asia**                   | **15,671** | **35,449**    |
| **Total**                  | **74,047** | **171,721**   |


### Positive Samples
Available soon

### Negative Samples
Available soon
