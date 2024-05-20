import os
import re
from bs4 import BeautifulSoup

dir_path = "/Users/timaltendorf/Library/CloudStorage/OneDrive-stud.tu-darmstadt.de/EDU/TU/24 SoSe/Statistische Modellierung/slides/"

table_of_contents = """<tbody id="yui_3_18_1_1_1716228320196_305">
<tr style="height: 50.8px;" id="yui_3_18_1_1_1716228320196_320">
<td style="height: 50.8px; text-align: center;" id="yui_3_18_1_1_1716228320196_319"><strong>Week</strong></td>
<td style="height: 50.8px; text-align: center;"><strong>Reading and Questions for Lecture<br></strong></td>
<td style="height: 50.8px; text-align: center;"><strong>Literature (Mandatory)<br></strong></td>
<td style="text-align: center; height: 50.8px;"><strong>Additional Material<br></strong></td>
</tr>
<tr style="height: 83px;" id="yui_3_18_1_1_1716228320196_316">
<td style="height: 83px; width: 81pt;" width="108" height="18">15.04. - 21.04.<br>Week 01</td>
<td style="height: 83px; width: 167pt;" width="222" height="18">Recap &amp; Probability Theory (22.04.)</td>
<td style="height: 83px;" id="yui_3_18_1_1_1716228320196_315">
<p id="yui_3_18_1_1_1716228320196_314"><a href="https://moodle.tu-darmstadt.de/pluginfile.php/2484192/mod_page/content/25/DBDA-Chapter4.pdf" target="_blank" rel="noopener" id="yui_3_18_1_1_1716228320196_313">[DBDA]</a> Chapter 4.1 - 4.3</p>
<p><a href="https://probml.github.io/pml-book/book1.html" target="_blank" rel="noopener">[PMLI]</a> Chapter 2.1 &amp; 2.2</p>
</td>
<td style="text-align: center; height: 83px;"><span class="" style="color: rgb(0, 90, 169);">&nbsp;-</span></td>
</tr>
<tr style="height: 155px;" id="yui_3_18_1_1_1716228320196_312">
<td style="height: 155px;" height="18">22.04. - 28.04.<br>Week 02</td>
<td style="height: 155px;" height="18">Conditional Probability (29.04.)</td>
<td style="height: 155px;" id="yui_3_18_1_1_1716228320196_311">
<p><a href="https://moodle.tu-darmstadt.de/pluginfile.php/2484192/mod_page/content/25/DBDA-Chapter4.pdf" target="_blank" rel="noopener">[DBDA]</a> Chapter 4.4</p>
<p><a href="https://probml.github.io/pml-book/book1.html" target="_blank" rel="noopener">[PMLI]</a> Chapter 4.1 &amp; 4.2</p>
</td>
<td style="height: 155px;">
<p>(1) <a href="https://moodle.tu-darmstadt.de/pluginfile.php/2484192/mod_page/content/25/Bar-Hillel_Falk_1982.pdf" target="_blank" rel="noopener"><span class="" style="color: rgb(0, 90, 169);">Bar-Hillel, M., &amp; Falk, R. (1982). Some teasers concerning conditional probabilities.Cognition, 11(2), 109-122</span></a></p>
<p>(2) <a href="https://www.inference.org.uk/itprnn/book.pdf" target="_blank" rel="noopener">[ITILA]</a> Chapter 2.1 &amp; 2.2</p>
</td>
</tr>
<tr style="height: 595px;" id="yui_3_18_1_1_1716228320196_318">
<td style="height: 595px;" height="18">29.04. - 05.05.<br>Week 03</td>
<td class="xl75" style="height: 595px;" height="18">Bayes Theorem + Analytical Bayes (06.05.)</td>
<td style="height: 595px;" id="yui_3_18_1_1_1716228320196_317">&nbsp;
<p dir="ltr" style="text-align: left;" id="yui_3_18_1_1_1712755427733_512"><span><a href="https://moodle.tu-darmstadt.de/pluginfile.php/2484232/mod_page/content/7/DBDA-Chapter5.pdf" target="_blank" rel="noopener">[DBDA]</a> Chapter 5.1 - 5.4, 6<br></span></p>
<p dir="ltr" style="text-align: left;"><span><a href="https://probml.github.io/pml-book/book1.html" target="_blank" rel="noopener">[PMLI]</a> Chapter 4.3, 4.6 - 4.6.2, 4.6.4<br></span></p>
</td>
<td style="height: 595px;">
<p dir="ltr" style="text-align: left;"><span><a href="https://www.youtube.com/watch?v=HZGCoVF3YvM" target="_blank" rel="noopener"><span class="" style="color: rgb(0, 90, 169);">(1) 3Blue1Brown video on Bayes' Theorem</span></a><br>A very intuitive explanation of Bayes' Theorem, which uses examples from Kahneman &amp; Tversky's work!<br></span></p>
<p dir="ltr" style="text-align: left;"><span><span class="" style="color: rgb(0, 90, 169);">(2) </span><a href="https://moodle.tu-darmstadt.de/pluginfile.php/2484232/mod_page/content/7/1_Bayesian_Modelling_of_Visual_Perception.pdf?time=1618868687698" target="_blank" rel="noopener"><span class="" style="color: rgb(0, 90, 169);">Pascal Mamassian, Michael Landy and Laurence T. Maloney: Chapter 1 ”Bayesian Modelling of Visual Perception” in R. P. N. Rao, B. A. Olshausen &amp; M. S. Lewicki (Eds.) (2002). Probabilistic Models of the Brain, Cambridge, MA: MIT Press.</span></a><br>This book chapter shows you (without going into mathematical details) how Bayesian inference can be used as a model of visual perception, an idea which you will encounter again and again in recent computational cognitive science papers.</span></p>
<p dir="ltr">(3) <a href="https://www.inference.org.uk/itprnn/book.pdf" target="_blank" rel="noopener"><span class="" style="color: rgb(0, 90, 169);">[ITILA]</span></a> Chapter 2.3</p>
<p dir="ltr">(4) <a href="https://www.cns.nyu.edu/malab/bayesianbook.html"><span class="" style="color: rgb(0, 90, 169);">[BMP]</span></a> Chapter 1</p>
</td>
</tr>
<tr style="height: 83px;">
<td style="height: 83px;" height="18">06.05. - 12.05.<br>Week 04</td>
<td style="height: 83px;" height="18">Graphical Models (13.05.)</td>
<td style="height: 83px;">
<p dir="ltr" style="text-align: left;"><span data-inplaceeditable="1" data-component="core_course" data-itemtype="activityname" data-itemid="519384" data-value="[BMP] Chapter 6.1 &amp; 6.2" data-editlabel="Neuer Name für Aktivität [BMP] Chapter 6.1 &amp;amp; 6.2" data-type="text" data-options=""><span><a href="https://www.microsoft.com/en-us/research/people/cmbishop/prml-book/" target="_blank" rel="noopener">[PRML]</a> Chapter 8.1 - 8.2</span></span></p>
<p dir="ltr" style="text-align: left;"><span data-inplaceeditable="1" data-component="core_course" data-itemtype="activityname" data-itemid="519384" data-value="[BMP] Chapter 6.1 &amp; 6.2" data-editlabel="Neuer Name für Aktivität [BMP] Chapter 6.1 &amp;amp; 6.2" data-type="text" data-options=""><span><a href="https://probml.github.io/pml-book/book1.html">[PMLI]</a><span class="" style="color: rgb(0, 90, 169);"><span class="" style="color: rgb(0, 0, 0);"> Chapter 3.6</span></span></span></span></p>
</td>
<td style="height: 83px;">
<p><span data-inplaceeditable="1" data-component="core_course" data-itemtype="activityname" data-itemid="519384" data-value="[BMP] Chapter 6.1 &amp; 6.2" data-editlabel="Neuer Name für Aktivität [BMP] Chapter 6.1 &amp;amp; 6.2" data-type="text" data-options=""><span><span class="" style="color: rgb(0, 0, 0);"><u><a href="https://bayesmodels.com" target="_blank" rel="noopener">[BCM]</a></u> Chapters 3 &amp; 4<br></span></span></span></p>
</td>
</tr>
<tr style="height: 51px;">
<td style="height: 51px;" height="18">13.05. - 19.05.<br>Week 05</td>
<td class="xl76" style="height: 51px;" height="18"><em><strong>ENTFÄLLT </strong></em>(Pfingstmontag, 20.05.)</td>
<td style="height: 51px; text-align: center;">-</td>
<td style="text-align: center; height: 51px;">-</td>
</tr>
<tr style="height: 51px;">
<td style="height: 51px;" height="18">20.05. - 26.05.<br>Week 06</td>
<td class="xl75" style="height: 51px;" height="18">Markov Chain Monte Carlo (MCMC) (27.05.)</td>
<td style="height: 51px; text-align: center;">
<p dir="ltr" style="text-align: left;"><a href="https://moodle.tu-darmstadt.de/pluginfile.php/2484192/mod_page/content/25/DBDA-Chapter7.pdf">[DBDA]</a> Chapter 7.1-7.3</p>
</td>
<td style="height: 51px; text-align: left;">
<p>For a mathematical / computer science view on the topic, see <a href="https://probml.github.io/pml-book/book2.html">[PML2]</a> Chapter 12.1-12.2</p>
<p>To see a visualization, how these algorithms work, check out this <a href="http://chi-feng.github.io/mcmc-demo/app.html">website</a>. (The closest algorithm on that site to the reading material is called "RandomWalkMH")</p>
</td>
</tr>
<tr style="height: 83px;">
<td style="height: 83px;" height="18">27.05. - 02.06.<br>Week 07</td>
<td style="height: 83px;" height="18">Hierarchical Models (03.06.)</td>
<td style="height: 83px; text-align: center;">
<p dir="ltr" style="text-align: left;"><a href="https://bayesmodels.com/" target="_blank" rel="noopener">[BCM]</a> Chapter 6</p>
<p dir="ltr" style="text-align: left;"><a href="https://moodle.tu-darmstadt.de/pluginfile.php/2484260/mod_page/content/5/DBDA_Chapter9.pdf" target="_blank" rel="noopener">[DBDA]</a> Chapter 9</p>
</td>
<td style="height: 83px; text-align: left;"><span>for a more mathematical treatment see <a href="https://www.stat.columbia.edu/~gelman/book/BDA3.pdf" target="_blank" rel="noopener">[BDA]</a> Chapter 5<br></span></td>
</tr>
<tr style="height: 51px;">
<td style="height: 51px;" height="18">03.06. - 09.06.<br>Week 08</td>
<td style="height: 51px;" height="18">Linear Models for Regression (10.06.)</td>
<td style="height: 51px;"><a href="https://probml.github.io/pml-book/book1.html"><span class="" style="color: rgb(0, 131, 204);">[PMLI]</span></a><span id="yui_3_18_1_1_1712755752487_487"> Chapter 11.1 - 11.4, 11.7</span></td>
<td style="text-align: center; height: 51px;">-</td>
</tr>
<tr style="height: 75px;">
<td style="height: 75px;" height="18">10.06. - 16.06.<br>Week 09</td>
<td style="height: 75px;" height="18">General(ized) Linear Models I (17.06.)</td>
<td style="height: 75px;"><span class="" style="color: rgb(0, 90, 169);"><a href="https://bayesiancomputationbook.com/markdown/chp_03.html" target="_blank" rel="noopener">[BMCP]</a></span> Chapter 3.1, Chapter 3.2 (without 3.2.3), Chapter 3.3 (without 3.3.1), 3.4&nbsp;</td>
<td style="text-align: center; height: 75px;">-</td>
</tr>
<tr style="height: 51px;">
<td style="height: 51px;" height="18">17.06. - 23.06.<br>Week 10</td>
<td style="height: 51px;" height="18">General(ized) Linear Models II (23.06.)</td>
<td style="height: 51px;"><a href="https://bayesiancomputationbook.com/markdown/chp_04.html" target="_blank" rel="noopener">[BMCP]</a> Chapter 4.1 - 4.6 (without 4.6.1 and 4.6.2)</td>
<td style="text-align: center; height: 51px;">-</td>
</tr>
<tr style="height: 51px;">
<td style="height: 51px;" height="18">24.06. - 30.06.<br>Week 11</td>
<td class="xl75" style="height: 51px;" height="18">Model Comparison (30.06.)</td>
<td style="height: 51px; text-align: center;">TBD</td>
<td style="text-align: center; height: 51px;">TBD</td>
</tr>
<tr style="height: 51px;">
<td style="height: 51px;" height="18">01.07. - 07.07.<br>Week 12</td>
<td class="xl75" style="height: 51px;" height="18">TBD (08.07.)</td>
<td style="height: 51px; text-align: center;">TBD</td>
<td style="text-align: center; height: 51px;">TBD</td>
</tr>
<tr style="height: 51px;">
<td style="height: 51px;" height="18">08.07. - 14.07.<br>Week 13</td>
<td style="height: 51px;" height="18">Recap &amp; Exam Prep (15.07.)</td>
<td style="height: 51px; text-align: center;">-</td>
<td style="text-align: center; height: 51px;">-</td>
</tr>
</tbody>"""

# Parse the HTML
soup = BeautifulSoup(table_of_contents, "html.parser")

# Extract all rows
rows = soup.find_all("tr")[1:]  # skip the header row


# Function to clean and extract text
def clean_text(tag):
    return " ".join(tag.stripped_strings) if tag else "-"


# Function to format links
def format_links(tag):
    if not tag:
        return []
    return [f"{clean_text(a)} ({a['href']})" for a in tag.find_all("a")]


# Process each row and generate the text files
for row in rows:
    cells = row.find_all("td")

    week_info = clean_text(cells[0])
    lecture_info = clean_text(cells[1])
    literature_links = format_links(cells[2])
    additional_material_links = format_links(cells[3])

    # Extract week number for file naming
    week_number = re.search(r"Week (\d+)", week_info).group(1)

    # Create content for the file
    content = f"For lecture: {lecture_info}\n\nLiterature:\n"
    content += "\n".join([f"- {link}" for link in literature_links])
    content += "\n\nAdditional Material:\n"
    content += "\n".join([f"- {link}" for link in additional_material_links if link])

    # File name
    file_name = f"{week_number.zfill(2)}_VL_{week_number.zfill(2)}.pdf"
    file_path = os.path.join(dir_path, file_name)

    # Write to file
    with open(file_path, "w") as file:
        file.write(content)

print("Files created successfully!")
