let msnry = new Masonry( '.grid', {
    itemSelector: '.grid-item',
    // columnWidth: '.grid__col-sizer',
    // gutter: '.grid__gutter-sizer',
    columnWidth: 400,
    isFitWidth: true,
    stagger: 30,
    gutter: 10,
    visibleStyle: {
      transform: 'translateY(0)',
      opacity: 1,
    },
    hiddenStyle: {
      transform: 'translateY(100px)',
      opacity: 0,
    },
} );

// lazyload();

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

// eopenPhotoSwipe();

// window.onload = function() {
//     var grids = document.getElementsByClassName('grid-item');
//     for(var i = 0; i < grids.length; i++) {
//         var grid = grids[i];
//         print(grid);
//         grid.onclick = function() {
//             openPhotoSwipe(Number(grid.getAttribute('grid-id')));
//         }
//     }
// }
