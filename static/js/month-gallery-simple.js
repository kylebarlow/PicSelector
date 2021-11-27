var openPhotoSwipe = function(mediaIndex) {
    var pswpElement = document.querySelectorAll('.pswp')[0];
    
    // define options (if needed)
    var options = {
      	// history: false,
      	// focus: false,

        showAnimationDuration: 0,
        hideAnimationDuration: 0,
        index: mediaIndex // start at first slide
    };
    
    var gallery = new PhotoSwipe( pswpElement, PhotoSwipeUI_Default, items, options);
    gallery.init();
};
