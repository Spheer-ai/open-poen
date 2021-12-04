// Import external dependencies
import * as d3 from 'd3';
import 'jquery';
import 'bootstrap';
import 'ekko-lightbox/dist/ekko-lightbox.min.js';
import 'bootstrap-table';
import 'bootstrap-table/dist/locale/bootstrap-table-nl-NL.min.js';
import 'bootstrap-table/dist/extensions/sticky-header/bootstrap-table-sticky-header.min.js';
import 'bootstrap-table/dist/extensions/mobile/bootstrap-table-mobile.min.js';
import 'tableexport.jquery.plugin/tableExport.min.js';
import 'bootstrap-table/dist/extensions/export/bootstrap-table-export.min.js';
import 'bootstrap-table/dist/extensions/cookie/bootstrap-table-cookie.min.js';
import naturalSort from 'javascript-natural-sort';
import datepicker from 'js-datepicker';

// Import local dependencies
import Router from './util/Router';
import common from './routes/common';
import home from './routes/home';
import transaction from './routes/transaction';

// Import the needed Font Awesome functionality
import { config, library, dom } from '@fortawesome/fontawesome-svg-core';
// Import required icons
import { faBars, faChevronDown, faFile, faCamera, faDownload, faReceipt, faWindowRestore } from '@fortawesome/free-solid-svg-icons';
import moment from 'moment';

// Add the imported icons to the library
library.add(faBars, faChevronDown, faFile, faCamera, faDownload, faReceipt);

// Tell FontAwesome to watch the DOM and add the SVGs when it detects icon markup
dom.watch();

// Populate Router instance with DOM routes
const routes = new Router({
  // All pages
  common,
  // Home page
  home,
  // Project and Subproject pages can add new transactions
  transaction,
});

// Load events
$(document).ready(() => routes.loadEvents());

// Used for sorting amounts in the payment tables. It filters the amounts from the HTML, replaces the comma with a dot and removes white space (thousand separators).
window.customSort = function(a, b) {
  var aa = a.match('[^>]*>(.*)</h1>')[1].replace(',', '.').replace(/\s/g, '');
  var bb = b.match('[^>]*>(.*)</h1>')[1].replace(',', '.').replace(/\s/g, '');
  return naturalSort(aa, bb);
};

// Needed to sort dates in payment tables
window.sortByDate = function(a, b) {
  var aValue = moment(a, "DD-MM-'YY").format('YYYYMMDD');
  if (a === '' || a === null) { aValue = 0; }

  var bValue = moment(b, "DD-MM-'YY").format('YYYYMMDD');
  if (b === '' || b === null) { bValue = 0; }

  return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
}

// Format detail view of payment table row
window.detailFormatter = function(index, row) {
  var id = row[0].match(/>\s+(\d+)\s+<\/div>/)[1]
  return $('#detail-' + id).html()
}

// Create a donut with of the spent percentage
window.donut = function(thisObj) {
  // Clear HTML, otherwise you generate more donuts when resizing the window
  $(thisObj).html('');

  // Get the percentage from this custom attribute we set
  var uses = parseInt($(thisObj).attr('data-percentage'));

  var chart = d3.select(thisObj);

  var width = $(thisObj).width();

  var height = width;

  var radius = Math.min(width, height) / 2;

  var color = d3.scale.ordinal()
    .range(["#b82466", "#265ed4"]);

  var arc = d3.svg.arc()
    .outerRadius(radius)
    .innerRadius(radius - width / 6);

  var pie = d3.layout.pie()
    .value(function (d) {
    return d.value;
  }).sort(null);

  chart = chart
    .append('svg')
    .attr("width", width)
    .attr("height", height)
    .append("g")
    .attr("transform", "translate(" + (width / 2) + "," + (height / 2) + ")");

  // just abort and leave it blank if something's wrong
  // (instead of showing "NaN%" visually)
  if (isNaN(uses))
    return;

  var pie_uses = uses;
  if (uses > 100) {
    pie_uses = 100;
  }
  var pie_data = [
    {status: 'active', value: pie_uses},
    {status: 'inactive', value: (100 - pie_uses)},
  ]

  var g = chart.selectAll(".arc")
    .data(pie(pie_data))
    .enter().append("g")
    .attr("class", "arc");

  g.append("path")
    .style("fill", function(d) {
    return color(d.data.status);
  })
    .transition().delay(function(d, i) {
    return i *400;
  }).duration(400)
    .attrTween('d', function(d) {
    var i = d3.interpolate(d.startAngle+ 0.1, d.endAngle);
    return function(t) {
      d.endAngle = i(t);
      return arc(d);
    }
  });

  // Add text inside the donut
  g.append("text")
    .attr("text-anchor", "middle")
    .attr("font-size", "10")
    .attr("class", "total-type")
    .attr("dy", "-0.2em")
    .attr("fill", "#000059")
    .text(function(d){
      return "besteed";
  });

  // Add percentage inside the donut
  g.append("text")
    .attr("text-anchor", "middle")
    .attr("font-size", "10")
    .attr("class", "total-type")
    .attr("class", "total-value")
    .attr("dy", "1.0em")
    .attr("fill", "#000059")
    .text(function(d){
      return "" + uses + "%";
  });
}

window.createDonuts = function() {
  $('.donut').each(function() {window.donut(this)});
}

createDonuts();

// We render a template with a modal_id if if we want the modal to
// pop up at the loading of the page, such as when we load a page
// with a form with validation errors.
$(window).on('load', function() {
  if (typeof window.modal_id !== "undefined") {
    $(window.modal_id).modal('show');
  }
});

// Prevents sending the form again when reloading the page.
if ( window.history.replaceState ) {
  window.history.replaceState( null, null, window.location.href );
}

var datepickerConfig = {
  startDay: 1,
  customDays: ["ma", "di", "wo", "do", "vr", "za", "zo"],
  customMonths: ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"],
  overlayButton: "Invoeren",
  overlayPlaceholder: "Voer een jaar in",
  formatter: (input, date, instance) => {
    const value = date.toLocaleDateString("nl-NL");
    input.value = value;
  }
}

// Simpelest case of setting a datepicker.
if ($(".datepicker").length > 0) {
  var picker = datepicker(".datepicker", datepickerConfig);
}

// Setting datepickers for the detail views of the bootstrap tables.
// The ordinary way is impossible, because of the way the page loads.
// We therefore have to dynamically assign and remove these date pickers
// on expanding and collapsing detail views respectively. Nevertheless,
// there is surely a better way of doing this.
window.datepicker = datepicker;
window.tableDatePickers = {};

$('.payment-table').bootstrapTable({
  onExpandRow: function (index, row, detailView) {
    var dateInput = $(detailView).find(".table-datepicker");
    if (dateInput.length > 0) {
      var className = "active-table-datepicker" + index;
      dateInput.addClass(className)
      window.tableDatePickers[className] = window.datepicker("." + className, datepickerConfig);
    }
  },
  onCollapseRow: function (index, row, detailView) {
    var className = "active-table-datepicker" + index;
    if (className in window.tableDatePickers) {
      window.tableDatePickers[className].remove();
      delete window.tableDatePickers[className];
    }
  },
  // Sorting changes the indices of the table rows and collapses all
  // of them. To ensure window.tableDatePickers stays in sync, we
  // delete all datepickers previously instantiated.
  onSort: function (name, order) {
    for (var key in window.tableDatePickers) {
      window.tableDatePickers[key].remove();
      delete window.tableDatePickers[key];
    }
  }
});

// This is used to guide back the user to the payment that failed to
// be updated in the payments table because of for example invalid input.
window.scrollToPayment = function(paymentId) {
  var row = $("#payment_row_" + paymentId);
  var dataIndex = row.attr("data-index");
  $('.payment-table').bootstrapTable("toggleDetailView", parseInt(dataIndex));
  $([document.documentElement, document.body]).animate({
    scrollTop: $("#payment_row_" + paymentId).offset().top
  }, 400);
}