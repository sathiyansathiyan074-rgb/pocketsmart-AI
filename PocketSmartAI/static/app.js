document.addEventListener(
    "DOMContentLoaded",
    function () {

        const fileInputs =
            document.querySelectorAll(
                'input[type="file"]'
            );

        fileInputs.forEach(
            function (input) {

                input.addEventListener(
                    "change",
                    function () {

                        const file =
                            input.files[0];

                        if (!file) {
                            return;
                        }

                        const maxSize =
                            8 * 1024 * 1024;

                        if (
                            file.size >
                            maxSize
                        ) {

                            alert(
                                "Maximum image size is 8 MB."
                            );

                            input.value = "";
                        }
                    }
                );
            }
        );

    }
);