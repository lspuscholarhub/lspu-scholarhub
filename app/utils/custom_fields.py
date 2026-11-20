"""Parse the campus-defined questions on a scholarship form.

Staff and admin both build these from four parallel inputs: field_label[],
field_type[], field_options[] and field_required[]. The first three are text
inputs and always submit one value per row, so their positions line up.

The "Required" checkbox is different: an unticked box is not submitted at all,
so field_required[] holds only the rows that were ticked - and the template
gives each box its row index as its value, so the list arrives as those indices.
Comparing a row against a constant (the old value="1") made row 1 required no
matter what the box said, and defaulting the missing rows to required forced
optional questions on students.
"""

FIELD_TYPES = ('text', 'number', 'dropdown')


def parse_custom_fields(form):
    """Return the custom_form_fields JSON for a scholarship form submission."""
    labels = form.getlist('field_label[]')
    types = form.getlist('field_type[]')
    options_raw = form.getlist('field_options[]')
    required_rows = set(form.getlist('field_required[]'))

    fields = []
    for i, label in enumerate(labels):
        if not label.strip():
            continue
        ftype = types[i] if i < len(types) else 'text'
        options = None
        if ftype == 'dropdown' and i < len(options_raw):
            options = [o.strip() for o in options_raw[i].split(',') if o.strip()]
        fields.append({
            'label': label.strip(),
            'type': ftype,
            'required': str(i) in required_rows,
            'options': options,
        })
    return fields
