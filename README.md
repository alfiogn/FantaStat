# FantaStat
A tool to prepare for the "Asta del Fantacalcio". Fantalega on [Fantacalcio](https://www.fantacalcio.it/).

FantaStat is a plotly dashboard to analyse fanta-football data to prepare the auction.


## The data

It downloads all the necessary data, scraping them from the internet:
* Statistics for every year
* Serie A calendar and results
* Likely line-ups
* Footballers marks for the last n days

Data are visualized on the dashboard using a table. They can be:
* filtered through [header entries](https://dash.plotly.com/datatable/filtering)
* A dropdown menu allows to visualize statistics for different years or for the last n days
* The table can be exported in excel

Moreover, the user can write in the table cells in columns 'Flag', 'Slot' and 'Note'.
The notes can be backup by the 'Backup changes' button, as well as the Asta data in the top right corner.


## The Asta

The player bought during the Asta can be registered using the dropdown menus in the top left corner.
Then a player can be submitted to a team at a certain cost or it can be removed.

Asta data and spent millions are updated in the upper table. The team to which a player is assigned is
written in the main table, together with a flag 'Si'/'No' in the first column.



