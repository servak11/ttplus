// Show summary table below the Kommen/Gehen table
//
// in the applet "buchen"
// there are two containers
// - one for selector / Buchung / get. Buchungen / Abfrage /
// - one for showing content of respective tables - this one is divAll
//
// Issue: get. Buchungen only show Kommen und Gegen times, but not summary
// Task: also show summary (tblabfrage) below that table, because plenty space
//
// Top container is this one - do not modify it:
//const container = document.querySelector('.navcontainer');

const container = document.getElementById('divAll');
const table1 = document.getElementById('tblgetBuch');
const table2 = document.getElementById('tblabfrage');

if (container && table1 && table2) {
// Clear existing content - no, just append below
// because the functionality breaks if we clear this contained
//container.innerHTML = '';

// Make sure both tables are visible
//table1.style.display = 'block';
table2.style.display = 'block';

// Append both tables
//container.appendChild(table1);
container.appendChild(table2);
}