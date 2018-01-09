/**
 * Reset Password page
 */
'use strict';
var $ = require('jquery');
var passwordForms = require('js/passwordForms');

$(document).ready(function() {
    new passwordForms.SetPassword('#resetPasswordForm');

    // Rewrite url to remove token so it is not passed with document.referrer
    history.replaceState({}, 'Reset Password', '/resetpassword/');
});
