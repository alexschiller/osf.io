/**
 * Confirm Email page
 */
'use strict';
var $ = require('jquery');

$(document).ready(function() {

    // Rewrite url to remove token so it is not passed with document.referrer
    history.replaceState({}, 'Confirm', '/confirm/');
});
