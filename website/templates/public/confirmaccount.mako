<%inherit file="base.mako"/>
<%def name="title()">Confirm</%def>
<%def name="content()">
<h1 class="page-header text-center">Confirm email address?</h1>
<div class="row">
    <form class="form col-md-8 col-md-offset-2 m-t-xl text-center"
            id="confirmEmailForm"
            name="confirmEmailForm"
            method="POST"
            action="/confirm/${uid}/${token}/"
            >
        <div><b>${email}</b></div>
        <br>
        <button aria="confirm email address" type="submit" class="btn btn-primary m-t-md">Confirm</button>
    </form>
</div>

</%def>

<%def name="javascript_bottom()">
    <script type="text/javascript">
        window.contextVars = $.extend(true, {}, window.contextVars, {
            token: ${token | sjson, n}
        });
    </script>
    ${parent.javascript_bottom()}
    <script src=${"/static/public/js/confirmaccount-page.js" | webpack_asset}></script>
</%def>
