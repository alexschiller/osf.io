'use strict';

var ko = require('knockout');
var bootbox = require('bootbox');

var $osf = require('osfHelpers');

function FolderCreatorViewModel(params) {
    var self = this;
    self.params = params || {};

    self.url = '/api/v1/folder/' + self.params.data;
    self.hasFocus = params.hasFocus;
    self.title = ko.observable('').extend({
        maxLength: 200
    });

    self.formErrorText = ko.observable('');
    
    self.createFolder = function () {
        $osf.postJSON(
            self.url,
            self.serialize()
        ).done(
            self.createSuccess
        ).fail(
            self.createFailure
        );
    };

    self.createSuccess = function (data) {
        // window.location = data.projectUrl;
    };

    self.createFailure = function () {
        $osf.growl('Could not create a new folder.', 'Please try again. If the problem persists, email <a href="mailto:support@osf.io.">support@osf.io</a>');
    };

    self.serialize = function () {
        return {
            title: self.title()
        };
    };

    self.verifyTitle = function () {
        if (self.title() === ''){
            self.formErrorText('We need a title for your folder.');
        } else {
            self.createFolder();

            // -stupid reload function, better way?
            window.location = "/dashboard/";

        }
    };
 
}

ko.components.register('osf-folder-create-form', {
    viewModel: FolderCreatorViewModel,
    template: {element: 'osf-folder-create-form'}
});
