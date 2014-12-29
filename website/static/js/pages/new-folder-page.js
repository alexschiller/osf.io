
var FolderCreator = require('../folderCreator.js');

var nodeID = window.contextVars.nodeID;
new FolderCreator('#creationFolderForm', '/api/v1/folder/' + nodeID);
