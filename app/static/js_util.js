function formatDate(dateString) {
  let date = new Date(dateString);
  let day = date.getDate();
  let month = date.getMonth() + 1;
  let year = date.getFullYear();

  let hours = date.getHours();
  let minutes = date.getMinutes();

  return `${day}.${month}.${year} - ${hours}:${minutes}`;
}

function buildSelect(id, options, activeOption, isEditable) {
  let disabled = "";
  if (!isEditable) disabled = "disabled";

  let select = '<select class="custom-select" id="' + id + '"' + disabled + ">";
  if (activeOption == null)
    select += "<option selected>Not Assigned</option>\n";
  else select += "<option>Not Assigned</option>\n";

  for (let option of options) {
    if (option === activeOption) {
      select += "<option selected >" + option + "</option>\n";
    } else {
      select += "<option >" + option + "</option>\n";
    }
  }
  select += "</select>\n";
  return select;
}

// From here on: Author: jkriegel

/**
 * Default REST Fail is used to AJAX calls to display errors in console
 * @param {*} request
 * @param {*} status
 * @param {*} errorThrown
 */
function defaultRESTFail(request, status, errorThrown) {
  console.log(
    this.url + " responded with " + request.status,
    errorThrown,
    "\n",
    request.responseText
  );
}

/*
    Reducing keys like manual_segmentation.status and the object data { manual_segmentation: { status: "abc" }}
    to the value of status

    field_config.data = 'manual_segmentation.status'
    data = { manual_segmentation: { status: "abc" }}
    afterwards: start[1] = "abc"
    */
function getDeepElementFromObject(deepKey, object) {
  start = [deepKey.split("."), object];

  while (start[0].length > 0 && start[1]) {
    start = [start[0].splice(1, start[0].length - 1), start[1][start[0]]];
  }

  return start[1];
}

/*
    Checks whether the Datatables Editor could be loaded. If it could not be loaded,
    false is returned and a warning is displayed stating that the Datatables Editor
    should be loaded in order to use all functions.
    */
function isDatatablesLoaded(display_alert = true) {
  if (!$.fn.dataTable.Editor) {
    if (display_alert)
      alert(
        'Unfortunately the extension "Datatables Editor" could not be loaded. To use the full functionality of the platform, "Datatables Editor" is required. "Datatables Editor" can be purchased here: https://editor.datatables.net'
      );
    return false;
  }

  return true;
}
