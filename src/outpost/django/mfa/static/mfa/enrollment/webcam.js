(() => {

  const width = 1080;
  let height = 0;

  let streaming = false;

  let video = null;
  let canvas = null;
  let form = null;
  let image = null;

  function startup() {
    video = document.getElementById("video");
    canvas = document.getElementById("canvas");
    image = document.getElementById("image");
    form = document.getElementById("form");

    navigator.mediaDevices
      .getUserMedia({ video: true, audio: false })
      .then((stream) => {
        video.srcObject = stream;
        video.play();
      })
      .catch((err) => {
        console.error(`An error occurred: ${err}`);
      });

    video.addEventListener(
      "canplay",
      (ev) => {
        if (!streaming) {
          height = video.videoHeight / (video.videoWidth / width);

          if (isNaN(height)) {
            height = width / (4 / 3);
          }

          //video.setAttribute("width", width);
          //video.setAttribute("height", height);
          canvas.setAttribute("width", width);
          canvas.setAttribute("height", height);
          streaming = true;
        }
      },
      false,
    );

    form.addEventListener(
      "submit",
      (ev) => {
        const context = canvas.getContext("2d");
        ev.preventDefault();
        if (width && height) {
          canvas.width = width;
          canvas.height = height;
          context.drawImage(video, 0, 0, width, height);

          const data = canvas.toDataURL("image/png");
          image.value = data;

          video.pause();
          form.submit();
        }
      },
      false,
    );

  }

  window.addEventListener("load", startup, false);
})();
