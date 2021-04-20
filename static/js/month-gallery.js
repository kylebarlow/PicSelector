// let msnry = new Masonry( '.grid', {
//   itemSelector: '.grid-item',
//   // use element for option
//   columnWidth: '.grid-sizer',
//   percentPosition: true
// } );

// // lazyload();
var $grid = $('.grid').imagesLoaded( function() {
  // init Masonry after all images have loaded
  $grid.masonry({
    itemSelector: '.grid-item',
    // use element for option
    columnWidth: '.grid-sizer',
    gutter: '.gutter-sizer',
    percentPosition: true
  });
});

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
