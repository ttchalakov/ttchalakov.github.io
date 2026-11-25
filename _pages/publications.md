---
layout: page
permalink: /publications/
title: publications
description: peer-reviewed publications, then working papers, newest first.
nav: true
nav_order: 1
---

<!-- _pages/publications.md: entries come from _bibliography/papers.bib. Peer-reviewed papers are
@article and @inproceedings entries, papers under review are @unpublished entries (listed first,
with an "Under review" badge and no venue), and working papers are @techreport entries. -->

<!-- Bibsearch Feature -->

{% include bib_search.liquid %}

<div class="publications">

{% bibliography --query @unpublished,@article,@inproceedings %}

</div>

<h2 id="working-papers">Working Papers</h2>

<div class="publications">

{% bibliography --query @techreport %}

</div>
