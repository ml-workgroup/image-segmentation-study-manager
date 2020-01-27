function downloadCase(rowObject) {
    let project_id = rowObject["project_id"];
    let image_name = rowObject["name"];
    console.log("mist");
    $.ajax({
        url: '/data/download_case_data',
        type: 'GET',
        beforeSend: function (xhr) {
            xhr.setRequestHeader('project_id', project_id);
            xhr.setRequestHeader('image_name', image_name);
        },
        xhrFields: {
            responseType: 'blob'
        },
        success: function (data) {
            console.log("bla");
            let a = document.createElement('a');
            let url = window.URL.createObjectURL(data);
            a.href = url;
            a.download = 'data.zip';
            document.body.append(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        },
        error: function (XMLHttpRequest, textStatus, errorThrown) {
            console.log("lol");
            location.reload();
        }
    });
}

// Function to make call to API after row has been updated
function sendRowUpdateToServer(rowObject) {
    $.ajax({
        type: 'POST',
        url: '/data/update_image_meta_data',

        data: JSON.stringify(rowObject),
        success: function (data) {
            console.log("success");
        },
        error: function (e) {
            console.log(e);
        },

        dataType: "json",
        contentType: "application/json"
    });
}

function formatDate(dateString){
    let date = new Date(dateString);
    let day = date.getDate();
    let month = date.getMonth() + 1;
    let year = date.getFullYear();

    let hours = date.getHours();
    let minutes = date.getMinutes();

    return `${day}.${month}.${year} - ${hours}:${minutes}`;
}