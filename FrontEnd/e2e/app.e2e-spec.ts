import { OpenDLabPage } from './app.po';

describe('open-dlab App', function() {
  let page: OpenDLabPage;

  beforeEach(() => {
    page = new OpenDLabPage();
  });

  it('should display message saying app works', () => {
    page.navigateTo();
    expect(page.getParagraphText()).toEqual('app works!');
  });
});
