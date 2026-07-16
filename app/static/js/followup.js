// Follow-up composer: picking a template swaps in its pre-rendered
// subject/body (substituted server-side for this job — see the
// #followup-prefill JSON tag). Clearing the picker empties both fields.
(function () {
    'use strict';

    var dataEl = document.getElementById('followup-prefill');
    var select = document.getElementById('template_id');
    if (!dataEl || !select) return;
    var prefill = JSON.parse(dataEl.textContent);

    select.addEventListener('change', function () {
        var entry = prefill[select.value];
        document.getElementById('subject').value = entry ? entry.subject : '';
        document.getElementById('body').value = entry ? entry.body : '';
    });
})();
