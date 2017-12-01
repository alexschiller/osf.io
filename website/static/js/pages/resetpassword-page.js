/**
 * Reset Password page
 */
'use strict';
var $ = require('jquery');
var passwordForms = require('js/passwordForms');

$(document).ready(function() {
    new passwordForms.SetPassword('#resetPasswordForm');

    // Rewrite url to remove token so it is not passed with document.referrer
    history.replaceState({}, "Reset Password", "/resetpassword/")
    // NOTEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE
    // NOTEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE
    // NOTEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE
    // NOTEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE
    // NOTEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE
    // NOTEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE
    // NOTEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE
    // NOTEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE
    // NOTEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE
    // This route needs to be real so they don't refresh and #404
});
